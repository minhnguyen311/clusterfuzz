# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Issue tracker policy."""

from collections import namedtuple

from clusterfuzz._internal.config import local_config
from clusterfuzz._internal.metrics import logs

Status = namedtuple('Status',
                    ['assigned', 'duplicate', 'wontfix', 'fixed', 'verified'])

EXPECTED_STATUSES = [
    'assigned',
    'duplicate',
    'wontfix',
    'fixed',
    'verified',
    'new',
]

EXTENSION_PREFIX = '_ext_'


class ConfigurationError(Exception):
  """Base configuration error class."""


class NewIssuePolicy:
  """New issue policy."""

  def __init__(self):
    self.status = ''
    self.ccs = []
    self.labels = []
    self.issue_body_footer = ''

    # Contains _ext_ prefixed extension fields. Eg: _ext_collaborators.
    self.extension_fields = {}


def _to_str_list(values):
  """Convert a list to a list of strs."""
  return [str(value) for value in values]


class IssueTrackerPolicy:
  """Represents an issue tracker policy."""

  def __init__(self, data):
    self._data = data
    if 'status' not in self._data:
      raise ConfigurationError('Status not set in policies.')

    if 'labels' not in self._data:
      raise ConfigurationError('Labels not set in policies.')

    for status in EXPECTED_STATUSES:
      if status not in self._data['status']:
        raise ConfigurationError(
            'Expected status {} is not set.'.format(status))

  def status(self, status_type):
    """Get the actual status string for the given type."""
    return self._data['status'][status_type]

  @property
  def extension_fields(self):
    """Returns all _ext_ prefixed data items."""
    extension_fields = {}
    # Extension fields are dynamically added to the policy
    # depending on which (if any) have been set in the config
    logs.log('extension_fields: self._data: %s' % self._data)
    for k, v in self._data.items():
      if k.startswith(EXTENSION_PREFIX):
        logs.log('extension_fields: Found %s with value %s' % (k, v))
        extension_fields[k] = v
    return extension_fields

  def label(self, label_type):
    """Get the actual label string for the given type."""
    label = self._data['labels'].get(label_type)
    if label is None:
      return None

    return str(label)

  def label_for_crash_type(self, crash_type):
    """Get the actual label string for the given crash type."""
    if 'crash_types' not in self._data['labels']:
      return None

    crash_type = crash_type.splitlines()[0].lower()
    label = self._data['labels']['crash_types'].get(crash_type)
    if label is None:
      return None

    return str(label)

  def label_for_crash_category(self, crash_category):
    """Get the actual label string for the given crash subtype."""
    if 'crash_categories' not in self._data['labels']:
      return None

    crash_category = crash_category.splitlines()[0].lower()
    label = self._data['labels']['crash_categories'].get(crash_category)
    if label is None:
      return None

    return str(label)

  def substitution_mapping(self, label):
    """Get an explicit substitution mapping."""
    if 'substitutions' not in self._data:
      return label

    mapped = self._data['substitutions'].get(label)
    if not mapped:
      return label

    return str(mapped)

  @property
  def deadline_policy_message(self):
    """Get the deadline policy message, if it exists."""
    return self._data.get('deadline_policy_message')

  @property
  def unreproducible_component(self):
    """Get the component for unreproducible bugs, if it exists."""
    return self._data.get('unreproducible_component')

  @property
  def fallback_component(self):
    """Get the component for fallback (when save fails) issues, if it exists."""
    return self._data.get('fallback_component')

  @property
  def fallback_policy_message(self):
    """Get the fallback policy message, if it exists."""
    return self._data.get('fallback_policy_message')

  def get_new_issue_properties(self, is_security, is_crash):
    """Get the properties to apply to a new issue."""
    policy = NewIssuePolicy()

    if 'all' in self._data:
      self._apply_new_issue_properties(policy, self._data['all'], is_crash)

    if is_security:
      if 'security' in self._data:
        self._apply_new_issue_properties(policy, self._data['security'],
                                         is_crash)
    else:
      if 'non_security' in self._data:
        self._apply_new_issue_properties(policy, self._data['non_security'],
                                         is_crash)

    return policy

  def _apply_new_issue_properties(self, policy, issue_type, is_crash):
    """Apply issue policies."""
    if not issue_type:
      return

    if 'status' in issue_type:
      policy.status = self._data['status'][issue_type['status']]

    if 'ccs' in issue_type:
      policy.ccs.extend(issue_type['ccs'])

    labels = issue_type.get('labels')
    if labels:
      policy.labels.extend(_to_str_list(labels))

    issue_body_footer = issue_type.get('issue_body_footer')
    if issue_body_footer:
      policy.issue_body_footer = issue_body_footer

    if is_crash:
      crash_labels = issue_type.get('crash_labels')
      if crash_labels:
        policy.labels.extend(_to_str_list(crash_labels))
    else:
      non_crash_labels = issue_type.get('non_crash_labels')
      if non_crash_labels:
        policy.labels.extend(_to_str_list(non_crash_labels))

    for k, v in self.extension_fields:
      policy.extension_fields[k] = v

  def get_existing_issue_properties(self):
    """Get the properties to apply to a new issue."""
    policy = NewIssuePolicy()

    if 'existing' in self._data:
      self._apply_new_issue_properties(policy, self._data['existing'], False)

    return policy


def get(project_name):
  """Get policy."""
  issue_tracker_config = local_config.IssueTrackerConfig()
  project_config = issue_tracker_config.get(project_name)
  logs.log('project_name: %s' % project_name)
  logs.log('project_config: %s' % project_config)
  if not project_config:
    raise ConfigurationError(
        'Issue tracker for {} does not exist'.format(project_name))

  if not 'policies' in project_config:
    raise ConfigurationError(
        'Policies for {} do not exist'.format(project_name))

  return IssueTrackerPolicy(project_config['policies'])


def get_empty():
  """Get an empty policy."""
  return IssueTrackerPolicy({
      'status': {
          'assigned': 'unused',
          'duplicate': 'unused',
          'wontfix': 'unused',
          'fixed': 'unused',
          'verified': 'unused',
          'new': 'unused',
      },
      'labels': {},
  })
