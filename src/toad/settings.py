from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TypedDict, Required

from toad._loop import loop_last


@dataclass
class Setting:
    """A setting or group of setting."""

    key: str
    title: str
    type: str = "object"
    help: str = ""
    validate: list[dict] | None = None
    children: list[Setting] | None = None


class SchemaDict(TypedDict, total=False):
    """Typing for schema data structure."""

    key: Required[str]
    title: Required[str]
    type: Required[str]
    help: str
    default: object
    fields: list[SchemaDict]
    validate: list[dict]


type SettingsType = dict[str, object]


INPUT_TYPES = {"boolean", "integer", "string", "choices"}


class SettingsError(Exception):
    """Base class for settings related errors."""


class InvalidKey(SettingsError):
    """The key is not in the schema."""


class InvalidValue(SettingsError):
    """The value was not of the expected type."""


def parse_key(key: str) -> Sequence[str]:
    return key.split(".")


def get_setting[ExpectType](
    settings: dict[str, object], key: str, expect_type: type[ExpectType] = object
) -> ExpectType:
    """Get a key from a settings structure.

    Args:
        settings: A settings dictionary.
        key: A dot delimited key, e.g. "ui.column"
        expect_type: The expected type of the value.

    Raises:
        InvalidValue: If the value is not the expected type.
        KeyError: If the key doesn't exist in settings.

    Returns:
        The value matching they key.
    """
    for last, key_component in loop_last(parse_key(key)):
        if last:
            result = settings[key_component]
            if not isinstance(result, expect_type):
                raise InvalidValue(
                    f"Expected {expect_type.__name__} type; found {result!r}"
                )
            return result
        else:
            sub_settings = settings[key_component]
            assert isinstance(sub_settings, dict)
            settings = sub_settings
    raise KeyError(key)


class Schema:
    def __init__(self, schema: list[SchemaDict]) -> None:
        self.schema = schema

    def set_value(self, settings: SettingsType, key: str, value: object) -> None:
        schema = self.schema
        keys = parse_key(key)
        for last, key in loop_last(keys):
            if last:
                settings[key] = value
            if key not in schema:
                raise InvalidKey()
            schema = schema[key]
            assert isinstance(schema, dict)
            if key not in settings:
                settings = settings[key] = {}

    def build_default(self) -> dict[str, object]:
        settings: dict[str, object] = {}

        def set_defaults(schema: list[SchemaDict], settings: dict[str, object]) -> None:
            sub_settings: SettingsType
            for sub_schema in schema:
                key = sub_schema["key"]
                assert isinstance(sub_schema, dict)
                type = sub_schema["type"]
                if type in INPUT_TYPES:
                    if (default := sub_schema.get("default")) is not None:
                        settings[key] = default

                elif type == "object":
                    if fields := sub_schema.get("fields"):
                        sub_settings = settings[key] = {}
                        set_defaults(fields, sub_settings)

                elif type == "list":
                    data_settings = settings[key] = {}
                    item_fields = sub_schema.get("fields")
                    assert item_fields is not None

                    if defaults := sub_schema.get("default"):
                        assert isinstance(defaults, list)
                        for default in defaults:
                            default = default.copy()
                            item_key = default.pop("key")
                            sub_settings = data_settings[item_key] = default
                            set_defaults(item_fields, sub_settings)

        set_defaults(self.schema, settings)
        return settings

    def get_form_settings(self, settings: dict[str, object]) -> Sequence[Setting]:
        form_settings: list[Setting] = []

        def iter_settings(name: str, schema: SchemaDict) -> Iterable[Setting]:
            schema_type = schema.get("type")
            assert schema_type is not None
            if schema_type in INPUT_TYPES:
                yield Setting(
                    name,
                    schema["title"],
                    schema_type,
                    validate=schema.get("validate"),
                )

            elif schema_type == "object":
                yield Setting(
                    name,
                    schema["title"],
                    schema_type,
                    validate=schema.get("validate"),
                    children=[
                        setting
                        for schema in schema.get("fields", {})
                        for setting in iter_settings(f"{name}.{schema['key']}", schema)
                    ],
                )

            elif schema_type == "list":
                yield Setting(
                    name,
                    schema["title"],
                    schema_type,
                    children=[
                        Setting(
                            f"{name}.{sub_name}",
                            "",
                            validate=schema.get("validate"),
                            children=[
                                setting
                                for child_schema in schema.get("fields", {})
                                for setting in iter_settings(
                                    f"{name}.{sub_name}.{child_schema['key']}",
                                    child_schema,
                                )
                            ],
                        )
                        for sub_name in get_setting(settings, name, dict)
                    ],
                )

        for schema in self.schema:
            form_settings.extend(
                iter_settings(schema["key"], schema),
            )
        return form_settings


class Settings:
    """Stores schema backed settings."""

    def __init__(self, schema: Schema, settings: dict[str, object]) -> None:
        self._schema = schema
        self._settings = settings

    def get[ExpectType](
        self, key: str, expect_type: type[ExpectType] = object
    ) -> ExpectType:
        from os.path import expandvars

        setting = get_setting(self._settings, key, expect_type=expect_type)
        if isinstance(setting, str):
            setting = expandvars(setting)
        return setting


if __name__ == "__main__":
    from rich import print
    from rich.traceback import install

    from toad.settings_schema import SCHEMA

    install(show_locals=True, width=None)

    schema = Schema(SCHEMA)
    settings = schema.build_default()
    print(settings)

    print(schema.get_form_settings(settings))
