"""polarstory: polars-native exploration and static reporting."""

from importlib.metadata import version

from polarstory import plots, stats, alerts
from polarstory.alerts import Alert
from polarstory.comparison import DatasetComparison, compare
from polarstory.explorer import Explorer, explore
from polarstory.inspect import Inspection, inspect
from polarstory.profile import Profile, ProfileOptions, VariableProfile, profile, profile_from_spec
from polarstory.report import Report, ReportItem
from polarstory.variables import Variables, Variable

__version__ = version('polarstory')

__all__ = [
    'DatasetComparison', 'compare', 'Inspection', 'inspect', 'Explorer', 'explore', 'Profile', 'ProfileOptions',
    'VariableProfile',
    'profile', 'profile_from_spec', 'Variables', 'Variable', 'Alert', 'alerts', 'Report', 'ReportItem', 'stats',
    'plots',
]
