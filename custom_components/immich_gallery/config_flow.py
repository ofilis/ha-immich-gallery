"""Config flow for Immich Gallery."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    ApiError,
    CannotConnect,
    ImageTooLarge,
    ImmichApiClient,
    InvalidAuth,
    InvalidResponse,
    InvalidUrlError,
    MissingPermission,
    RateLimited,
    UnsupportedImage,
    normalize_base_url,
)
from .const import (
    CONF_ALBUM_IDS,
    CONF_INCLUDE_FAVORITES,
    CONF_INCLUDE_LIBRARY,
    CONF_REFRESH_INTERVAL,
    CONF_REPEAT_WINDOW,
    DEFAULT_INCLUDE_FAVORITES,
    DEFAULT_INCLUDE_LIBRARY,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_REPEAT_WINDOW,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_REFRESH_INTERVAL,
    MAX_REPEAT_WINDOW,
    MIN_REFRESH_INTERVAL,
    MIN_REPEAT_WINDOW,
)
from .models import Album, ValidationResult

_LOGGER = logging.getLogger(__name__)


def _connection_schema(
    defaults: Mapping[str, Any] | None = None,
    *,
    include_api_key: bool = True,
) -> vol.Schema:
    """Return the connection form schema."""
    defaults = defaults or {}
    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_URL,
            default=defaults.get(CONF_URL, ""),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
    }
    if include_api_key:
        schema[
            vol.Required(
                CONF_API_KEY,
                default=defaults.get(CONF_API_KEY, ""),
            )
        ] = TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        )
    schema[
        vol.Required(
            CONF_VERIFY_SSL,
            default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
    ] = bool
    return vol.Schema(schema)


def _source_schema(
    albums: tuple[Album, ...],
    current: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """Return a source selector using the modern multi-select control."""
    current = current or {}
    selected = current.get(CONF_ALBUM_IDS, [])
    selected_ids = selected if isinstance(selected, list) else []

    album_options = [
        SelectOptionDict(value=album.album_id, label=album.name) for album in albums
    ]
    known_ids = {album.album_id for album in albums}
    album_options.extend(
        SelectOptionDict(value=album_id, label=f"Unavailable album ({album_id[:8]})")
        for album_id in selected_ids
        if isinstance(album_id, str) and album_id not in known_ids
    )

    return vol.Schema(
        {
            vol.Required(
                CONF_INCLUDE_LIBRARY,
                default=current.get(
                    CONF_INCLUDE_LIBRARY,
                    DEFAULT_INCLUDE_LIBRARY,
                ),
            ): bool,
            vol.Required(
                CONF_INCLUDE_FAVORITES,
                default=current.get(
                    CONF_INCLUDE_FAVORITES,
                    DEFAULT_INCLUDE_FAVORITES,
                ),
            ): bool,
            vol.Optional(
                CONF_ALBUM_IDS,
                default=selected_ids,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=album_options,
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_REPEAT_WINDOW,
                default=current.get(
                    CONF_REPEAT_WINDOW,
                    DEFAULT_REPEAT_WINDOW,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_REPEAT_WINDOW,
                    max=MAX_REPEAT_WINDOW,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_REFRESH_INTERVAL,
                default=current.get(
                    CONF_REFRESH_INTERVAL,
                    DEFAULT_REFRESH_INTERVAL,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_REFRESH_INTERVAL,
                    max=MAX_REFRESH_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
        }
    )


def _normalize_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize mutable options for JSON-safe storage."""
    album_ids = user_input.get(CONF_ALBUM_IDS, [])
    return {
        CONF_INCLUDE_LIBRARY: bool(user_input.get(CONF_INCLUDE_LIBRARY)),
        CONF_INCLUDE_FAVORITES: bool(user_input.get(CONF_INCLUDE_FAVORITES)),
        CONF_ALBUM_IDS: (
            list(album_ids) if isinstance(album_ids, list | tuple) else []
        ),
        CONF_REPEAT_WINDOW: int(user_input[CONF_REPEAT_WINDOW]),
        CONF_REFRESH_INTERVAL: int(user_input[CONF_REFRESH_INTERVAL]),
    }


def _settings_schema(
    connection: Mapping[str, Any],
    albums: tuple[Album, ...],
    current: Mapping[str, Any],
) -> vol.Schema:
    """Return the Configure form for connection, sources, and rotation."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_URL,
            default=current.get(CONF_URL, connection[CONF_URL]),
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Optional(
            CONF_API_KEY,
            default="",
        ): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="new-password",
            )
        ),
        vol.Required(
            CONF_VERIFY_SSL,
            default=current.get(
                CONF_VERIFY_SSL,
                connection[CONF_VERIFY_SSL],
            ),
        ): bool,
    }
    schema.update(_source_schema(albums, current).schema)
    return vol.Schema(schema)


def _has_source(options: Mapping[str, Any]) -> bool:
    """Return whether at least one source is enabled."""
    album_ids = options.get(CONF_ALBUM_IDS, [])
    return bool(
        options.get(CONF_INCLUDE_LIBRARY)
        or options.get(CONF_INCLUDE_FAVORITES)
        or (isinstance(album_ids, list) and album_ids)
    )


async def _async_validate_connection(
    hass: HomeAssistant,
    data: Mapping[str, Any],
) -> tuple[dict[str, Any], ValidationResult]:
    """Normalize and validate a connection."""
    base_url = normalize_base_url(str(data[CONF_URL]))
    verify_ssl = bool(data[CONF_VERIFY_SSL])
    normalized = {
        CONF_URL: base_url,
        CONF_API_KEY: str(data[CONF_API_KEY]),
        CONF_VERIFY_SSL: verify_ssl,
    }
    client = ImmichApiClient(
        async_get_clientsession(hass, verify_ssl),
        base_url,
        normalized[CONF_API_KEY],
    )
    return normalized, await client.async_validate()


def _map_error(error: BaseException) -> str:
    """Map API failures to translated form error keys."""
    if isinstance(error, InvalidUrlError):
        return "invalid_url"
    if isinstance(error, InvalidAuth):
        return "invalid_auth"
    if isinstance(error, MissingPermission):
        return "missing_permission"
    if isinstance(error, CannotConnect | RateLimited):
        return "cannot_connect"
    if isinstance(
        error,
        ApiError | ImageTooLarge | InvalidResponse | UnsupportedImage,
    ):
        return "invalid_response"
    return "unknown"


class ImmichGalleryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Immich Gallery config flow."""

    VERSION = 1

    _connection_data: dict[str, Any]
    _validation: ValidationResult

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Connect to and validate an Immich instance."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                (
                    self._connection_data,
                    self._validation,
                ) = await _async_validate_connection(self.hass, user_input)
            except (
                ApiError,
                CannotConnect,
                InvalidAuth,
                InvalidResponse,
                InvalidUrlError,
                ImageTooLarge,
                MissingPermission,
                RateLimited,
                UnsupportedImage,
            ) as err:
                errors["base"] = _map_error(err)
            except Exception:
                _LOGGER.exception("Unexpected error while validating Immich")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self._validation.user_id)
                self._abort_if_unique_id_configured()
                return await self.async_step_sources()

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_sources(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select gallery sources and refresh behavior."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _normalize_options(user_input)
            if not _has_source(options):
                errors["base"] = "no_sources"
            else:
                return self.async_create_entry(
                    title="Immich Gallery",
                    data=self._connection_data,
                    options=options,
                )

        return self.async_show_form(
            step_id="sources",
            data_schema=_source_schema(
                self._validation.albums,
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Start API-key reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Validate and store a replacement API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = {
                **entry.data,
                CONF_API_KEY: user_input[CONF_API_KEY],
            }
            try:
                normalized, validation = await _async_validate_connection(
                    self.hass,
                    new_data,
                )
            except (
                ApiError,
                CannotConnect,
                InvalidAuth,
                InvalidResponse,
                InvalidUrlError,
                ImageTooLarge,
                MissingPermission,
                RateLimited,
                UnsupportedImage,
            ) as err:
                errors["base"] = _map_error(err)
            except Exception:
                _LOGGER.exception("Unexpected error while reauthenticating Immich")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(validation.user_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=normalized,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change the Immich URL or TLS verification setting."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            candidate = {
                **entry.data,
                CONF_URL: user_input[CONF_URL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            }
            try:
                normalized, validation = await _async_validate_connection(
                    self.hass,
                    candidate,
                )
            except (
                ApiError,
                CannotConnect,
                InvalidAuth,
                InvalidResponse,
                InvalidUrlError,
                ImageTooLarge,
                MissingPermission,
                RateLimited,
                UnsupportedImage,
            ) as err:
                errors["base"] = _map_error(err)
            except Exception:
                _LOGGER.exception("Unexpected error while reconfiguring Immich")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(validation.user_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=normalized,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(
                {
                    CONF_URL: entry.data[CONF_URL],
                    CONF_VERIFY_SSL: entry.data[CONF_VERIFY_SSL],
                },
                include_api_key=False,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ImmichGalleryOptionsFlow:
        """Return the options flow."""
        return ImmichGalleryOptionsFlow()


class ImmichGalleryOptionsFlow(OptionsFlowWithReload):
    """Update the connection and gallery behavior, then reload once."""

    async def _async_get_albums(self) -> tuple[Album, ...]:
        """Fetch current albums for the selector."""
        entry = self.config_entry
        client = ImmichApiClient(
            async_get_clientsession(
                self.hass,
                entry.data[CONF_VERIFY_SSL],
            ),
            entry.data[CONF_URL],
            entry.data[CONF_API_KEY],
        )
        return await client.async_get_albums()

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage gallery options."""
        errors: dict[str, str] = {}
        entry = self.config_entry
        current = (
            user_input if user_input is not None else {**entry.data, **entry.options}
        )

        if user_input is not None:
            options = _normalize_options(user_input)
            if not _has_source(options):
                errors["base"] = "no_sources"
            else:
                replacement_api_key = str(user_input.get(CONF_API_KEY, "")).strip()
                candidate = {
                    **entry.data,
                    CONF_URL: user_input[CONF_URL],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                if replacement_api_key:
                    candidate[CONF_API_KEY] = replacement_api_key

                try:
                    normalized, validation = await _async_validate_connection(
                        self.hass,
                        candidate,
                    )
                except (
                    ApiError,
                    CannotConnect,
                    InvalidAuth,
                    InvalidResponse,
                    InvalidUrlError,
                    ImageTooLarge,
                    MissingPermission,
                    RateLimited,
                    UnsupportedImage,
                ) as err:
                    errors["base"] = _map_error(err)
                except Exception:
                    _LOGGER.exception("Unexpected error while updating Immich Gallery")
                    errors["base"] = "unknown"
                else:
                    if (
                        entry.unique_id is not None
                        and validation.user_id != entry.unique_id
                    ):
                        errors["base"] = "wrong_account"
                    else:
                        connection_changed = dict(entry.data) != normalized
                        options_changed = dict(entry.options) != options
                        self.hass.config_entries.async_update_entry(
                            entry,
                            data=normalized,
                        )
                        if connection_changed and not options_changed:
                            self.hass.config_entries.async_schedule_reload(
                                entry.entry_id
                            )
                        return self.async_create_entry(data=options)

        try:
            albums = await self._async_get_albums()
        except (
            ApiError,
            CannotConnect,
            InvalidAuth,
            InvalidResponse,
            InvalidUrlError,
            MissingPermission,
            RateLimited,
        ) as err:
            errors["base"] = _map_error(err)
            albums = ()
        except Exception:
            _LOGGER.exception("Unexpected error while fetching Immich albums")
            errors["base"] = "unknown"
            albums = ()

        schema_values = dict(current)
        schema_values[CONF_API_KEY] = ""
        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(
                entry.data,
                albums,
                schema_values,
            ),
            errors=errors,
        )
