"""Combobox form widgets: a native control first, an accessible listbox once the script runs.

Both render a real form control carrying the field name, so the value a browser posts is the same
whether or not the inline enhancement script in ``core/templates/core/_scripts.html`` ran.
"""

from collections.abc import Callable, Iterable
from typing import Any

from django import forms

type SuggestionSource = Iterable[str] | Callable[[], Iterable[str]]


def _add_class(attrs: dict[str, Any], name: str) -> None:
    existing = attrs.get("class")
    attrs["class"] = f"{existing} {name}" if existing else name


class ComboboxWidget(forms.Select):
    """A closed combobox: the posted value is always one of the rendered options.

    Renders a native ``<select>``; the script replaces it with a filterable listbox and keeps
    writing the chosen value back to it. A ``placeholder`` in ``attrs`` becomes the prompt of the
    enhanced input rather than an attribute a ``<select>`` has no use for.
    """

    template_name = "core/widgets/combobox.html"

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget: dict[str, Any] = context["widget"]
        widget["placeholder"] = widget["attrs"].pop("placeholder", "")
        _add_class(widget["attrs"], "combobox__select")
        return context


class CreatableComboboxWidget(forms.TextInput):
    """An open combobox: one of the suggestions, or any value typed, posted verbatim.

    Renders a native ``<input>`` bound to a ``<datalist>`` of suggestions, so an unlisted value is
    accepted with or without the script, and the suggestions stay reachable either way.

    ``suggestions`` is either a fixed iterable or a callable returning one; pass the callable when
    the list comes from the database, because a widget is built once and rendered for years.
    """

    template_name = "core/widgets/creatable_combobox.html"

    def __init__(
        self, attrs: dict[str, Any] | None = None, suggestions: SuggestionSource = ()
    ) -> None:
        super().__init__(attrs)
        self.suggestions: SuggestionSource = suggestions

    def _current_suggestions(self) -> list[str]:
        source = self.suggestions() if callable(self.suggestions) else self.suggestions
        return [str(suggestion) for suggestion in source]

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget: dict[str, Any] = context["widget"]
        identifier = widget["attrs"].get("id") or name
        widget["datalist_id"] = f"{identifier}-options"
        widget["suggestions"] = self._current_suggestions()
        widget["attrs"]["list"] = widget["datalist_id"]
        widget["attrs"].setdefault("autocomplete", "off")
        _add_class(widget["attrs"], "combobox__input")
        return context


class BrazilianDateWidget(forms.DateInput):
    """A typed date in `dd/mm/aaaa`, with a calendar the script can open beside it.

    Never ``type="date"``: that control is drawn in the browser's interface locale, so a date
    typed day first is read month first and stored months away with no error (B23). The posted
    value comes from the text input alone, so the form behaves identically with the script blocked.
    """

    template_name = "core/widgets/date.html"

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        widget: dict[str, Any] = context["widget"]
        _add_class(widget["attrs"], "dateinput__typed")
        widget["attrs"]["aria-describedby"] = f"id_{name}_help"
        return context
