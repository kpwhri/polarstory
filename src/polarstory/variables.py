"""Optional semantic descriptions used by reports, independent of polars dtypes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from polarstory.columns import ColumnSelection, select_columns
from polarstory.source import DataInput, DataSource, as_source

VariableKind = Literal['auto', 'categorical', 'numeric', 'temporal', 'text', 'identifier', 'ignore']


@dataclass(frozen=True)
class Variable:
    label: str | None = None
    kind: VariableKind = 'auto'
    description: str | None = None
    sensitive: bool = False
    order: tuple[str, ...] = ()
    value_labels: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ('auto', 'categorical', 'numeric', 'temporal', 'text', 'identifier', 'ignore'):
            raise ValueError(f'Unknown semantic kind: {self.kind}')


class Variables:
    """Column metadata; selectors are expanded against a specific source schema."""

    def __init__(self) -> None:
        self._rules: list[tuple[ColumnSelection, Variable]] = []

    def set(
            self,
            columns: ColumnSelection,
            *,
            label: str | None = None,
            kind: VariableKind = 'auto',
            description: str | None = None,
            sensitive: bool = False,
            order: list[str] | tuple[str, ...] = (),
            value_labels: dict[str, str] | None = None,
    ) -> Variables:
        """Add a reusable semantic-metadata rule for selected variables.
        
        Args:
            columns: Column name, sequence, or polars selector.
            label: Human-readable name for a single resolved column.
            kind: Optional semantic-type override.
            description: Description from the dataset dictionary.
            sensitive: Whether automatic reports should suppress values.
            order: Preferred category order.
            value_labels: Mapping of source codes to display labels.
        
        Returns:
            This Variables object, allowing chained configuration.
        
        """
        self._rules.append((columns, Variable(label, kind, description, sensitive,
                                              tuple(order), dict(value_labels or {}))))
        return self

    def resolve(self, data: DataInput | DataSource) -> dict[str, Variable]:
        """Resolve configured metadata rules against an input schema.
        
        Args:
            data: polars source or supported parquet input.
        
        Returns:
            Mapping from column names to Variable metadata.
        
        """
        source = as_source(data)
        resolved: dict[str, Variable] = {}
        for selection, value in self._rules:
            names = select_columns(source, selection)
            if value.label is not None and len(names) != 1:
                raise ValueError('A custom label requires selection of exactly one column')
            resolved.update({name: value for name in names})
        return resolved
