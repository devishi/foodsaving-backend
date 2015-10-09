from importlib import import_module, reload
from os.path import join as join_path, dirname
from os import walk
from sys import modules

from yunity.utils.tests.abc import BaseTestCase
import yunity


def _source_to_module(path, root_module_path, pysuffix='.py'):
    path = path[len(dirname(root_module_path)) + 1:-len(pysuffix)]
    path = path.replace('/', '.')
    return path


def iter_sources(root_module_path, pysuffix='.py'):
    def is_source(_):
        return _.endswith(pysuffix) and not _.startswith('__init__')

    for root, _, leaves in walk(root_module_path):
        for leaf in filter(is_source, leaves):
            yield join_path(root, leaf)


def iter_modules(root_module_path, excludes=None):
    def is_blacklisted(_):
        return excludes and any(_.startswith(exclude) for exclude in excludes)

    for source in iter_sources(root_module_path):
        module = _source_to_module(source, root_module_path)
        if not is_blacklisted(module):
            yield module


def import_or_reload(resource):
    module = modules.get(resource)
    if module:
        return reload(module)
    else:
        return import_module(resource)


class PytonIsValidTestCase(BaseTestCase):
    def test_all_modules_import_cleanly(self):
        self.given_data(root_module_path=yunity.__path__[0])
        self.given_data(excludes={
            'yunity.resources',                               # intgration test data files have side-effects
            'yunity.tests.integration.test_integration',      # integration test runner has side-effects
            'yunity.management.commands.create_sample_data',  # sample data command has side-effects
        })
        self.when_importing_modules()
        self.then_all_modules_import_cleanly()

    def when_importing_modules(self):
        self.exception = []
        for module in iter_modules(*self.args, **self.kwargs):
            try:
                import_or_reload(module)
            except Exception as e:
                self.exception.append((module, e))

    def then_all_modules_import_cleanly(self):
        for module, exception in self.exception:
            self.fail('{} did not import cleanly: {}'.format(module, exception.args[0]))