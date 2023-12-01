#!/usr/bin/env python3

import argparse
import TestConstants
import os
import os.path
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
from yaml import SafeLoader
from basic_interaction_tests import FedoraBasicIxnTests
from version_tests import FedoraVersionTests
from fixity_tests import FedoraFixityTests
from rdf_tests import FedoraRdfTests
from sparql_tests import FedoraSparqlTests
from transaction_tests import FedoraTransactionTests
from authz_tests import FedoraAuthzTests
from indirect_tests import FedoraIndirectTests
from camel_tests import FedoraCamelTests
from ssearch_tests import FedoraSimpleSearchTests
from archival_group_tests import FedoraArchivalGroupTests


class FedoraTestRunner:

    # Tuples of parameter name and mandatory status
    config_params = [
        (TestConstants.BASE_URL_PARAM, True),
        (TestConstants.ADMIN_USER_PARAM, True),
        (TestConstants.ADMIN_PASS_PARAM, True),
        (TestConstants.USER_NAME_PARAM, True),
        (TestConstants.USER_PASS_PARAM, True),
        (TestConstants.USER2_NAME_PARAM, True),
        (TestConstants.USER2_PASS_PARAM, True),
        (TestConstants.LOG_FILE_PARAM, False),
        (TestConstants.SELECTED_TESTS_PARAM, False),
        (TestConstants.SOLR_URL_PARAM, False),
        (TestConstants.TRIPLESTORE_URL_PARAM, False),
        ('debug_level', False),
        ('failed_only', False),
    ]
    config = {}
    logger = None

    tests = {
        'basic': FedoraBasicIxnTests,
        'version': FedoraVersionTests,
        'fixity': FedoraFixityTests,
        'rdf': FedoraRdfTests,
        'sparql': FedoraSparqlTests,
        'transaction': FedoraTransactionTests,
        'authz': FedoraAuthzTests,
        'indirect': FedoraIndirectTests,
        'search': FedoraSimpleSearchTests,
        'archivalgroup': FedoraArchivalGroupTests,
    }

    def set_up(self, setup_args):
        self.parse_cmdline_args(setup_args)
        self.check_config()

    def load_config(self, file, site):
        if os.path.exists(file):
            if os.access(file, os.R_OK):
                with open(file, 'r') as fp:
                    yml = load(fp.read(), Loader=SafeLoader)
                    self.config = yml.get(site)

    def get_tests(self) -> list:
        return list(self.tests.keys())

    def parse_cmdline_args(self, command_args):
        filename = eval('args.' + TestConstants.CONFIG_FILE_PARAM)
        if filename is not None:
            sitename = eval('args.' + TestConstants.SITE_NAME_PARAM)
            if sitename is not None:
                self.load_config(filename, sitename)
        for param_name, param_status in self.config_params:
            if param_name == TestConstants.CONFIG_FILE_PARAM or param_name == TestConstants.SITE_NAME_PARAM:
                continue
            try:
                tmpA = eval("args." + param_name)
                if tmpA is not None:
                    self.config[param_name] = tmpA
            except AttributeError:
                if param_status:
                    parser.error("Could not find configuration parameter {}".format(param_name))

    def check_config(self):
        for param_name, param_status in self.config_params:
            try:
                if self.config[param_name] is not None:
                    pass
            except KeyError:
                if param_status:
                    raise Exception("Missing config parameter (" + param_name + ")")

    def run_tests(self) -> dict:
        results = {}
        for chosen_test in self.config[TestConstants.SELECTED_TESTS_PARAM]:
            if chosen_test == 'all':
                for test_param, test_class in self.tests.items():
                    instance = test_class(self.config)
                    instance.run_tests()
                    results[instance.__class__.__name__] = instance.results
                if chosen_test == 'camel':
                    camel = FedoraCamelTests(self.config)
                    camel.run_tests()
            else:
                test_class = self.tests[chosen_test]
                instance = test_class(self.config)
                instance.run_tests()
                results[instance.__class__.__name__] = instance.results
        return results

    def report(self, test_results: dict):
        """ Print out the test results collected from the various tests. """
        if len(test_results) > 0:
            print("\n{:-^50}".format("Test Results"))
            for k, results in test_results.items():
                print(f"\nTest Class: {k}")
                for method, result in results.items():
                    if result['result'] and not self.config['failed_only']:
                        print(f"  Method: {method}, Result: Pass")
                    elif not result['result']:
                        print(f"  Method: {method}, Result: Failed, {result['message']}")

    def main(self, application_args):
        self.set_up(application_args)
        results = self.run_tests()
        self.report(results)


def csv_list(string):
    if ',' in string:
        output = list(set([x for x in string.split(',') if len(x) > 0]))
    elif len(string) > 0:
        output = string
    else:
        output = list()
    return output


class CSVAction(argparse.Action):
    """ Holds the valid keys for the csv list """
    valid_options = []

    def __init__(self, option_strings, dest, **kwargs):
        if 'csv_options' in kwargs:
            self.valid_options = kwargs['csv_options']
            del kwargs['csv_options']
        super(CSVAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, args, values, option_string=None):
        if isinstance(values, list):
            invalid = [x for x in values if x not in self.valid_options]
        else:
            invalid = [values] if values not in self.valid_options else []
            values = [values]

        if len(invalid) > 0:
            if len(invalid) == 1:
                exception_text = "The option \"{0}\" is not valid, choose from {1}"
            else:
                exception_text = "The options \"{0}\" are not valid, choose from {1}"

            raise argparse.ArgumentError(self, exception_text.format(",".join(invalid), ",".join(self.valid_options)))
        setattr(args, self.dest, values)


if __name__ == '__main__':
    tests = FedoraTestRunner()

    parser = argparse.ArgumentParser(description="Fedora Tester runs a series of tests against an instance of the "
                                                 "community implementation of the Fedora API specification.")
    parser.add_argument('-c', '--' + TestConstants.CONFIG_FILE_PARAM, dest=TestConstants.CONFIG_FILE_PARAM,
                        help="Location of the configuration file")
    parser.add_argument('-n', '--' + TestConstants.SITE_NAME_PARAM, dest=TestConstants.SITE_NAME_PARAM,
                        default="default", help="Select a specific site from your Yaml config file.")
    parser.add_argument('-b', '--' + TestConstants.BASE_URL_PARAM, dest=TestConstants.BASE_URL_PARAM,
                        help="Base url of the Fedora repository.")
    parser.add_argument('-a', '--' + TestConstants.ADMIN_USER_PARAM, dest=TestConstants.ADMIN_USER_PARAM,
                        help="Admin username")
    parser.add_argument('-s', '--' + TestConstants.ADMIN_PASS_PARAM, dest=TestConstants.ADMIN_PASS_PARAM,
                        help="Admin password")
    parser.add_argument('-u', '--' + TestConstants.USER_NAME_PARAM, dest=TestConstants.USER_NAME_PARAM,
                        help="First regular username")
    parser.add_argument('-p', '--' + TestConstants.USER_PASS_PARAM, dest=TestConstants.USER_PASS_PARAM,
                        help="First regular user password.")
    parser.add_argument('-j', '--' + TestConstants.USER2_NAME_PARAM, dest=TestConstants.USER2_NAME_PARAM,
                        help="Second regular username")
    parser.add_argument('-k', '--' + TestConstants.USER2_PASS_PARAM, dest=TestConstants.USER2_PASS_PARAM,
                        help="Second regular user password")
    parser.add_argument('-t', '--tests', dest="selected_tests", help='Comma separated list of which tests to run from '
                        '{0}. Defaults to running all tests'.format(", ".join(tests.get_tests())),
                        default=['all'], type=csv_list, action=CSVAction, csv_options=tests.get_tests())
    parser.add_argument('-v', dest='debug_level', action='store_const', const=1, default=0,
                        help='Show all test steps')
    parser.add_argument('--failed-only', dest='failed_only', action='store_true', default=False,
                        help='Only show failed tests')

    args = parser.parse_args()

    tests.main(args)
