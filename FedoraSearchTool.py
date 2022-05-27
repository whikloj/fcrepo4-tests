#!/bin/env python

import TestConstants as TC
import requests


class FedoraSearchTool(object):

    max_results = None
    offset = None
    order_by = None
    order = None
    baseUri = None
    fields = list()
    conditions = list()
    authz = None

    def __init__(self, base, authz):
        self.authz = authz
        self.baseUri = base

    @staticmethod
    def create(base_uri, calling_class):
        """
        Create a FedoraSearchTool instance
        :param base_uri: The base uri of the fedora instance.
        :param calling_class: The test class this is used in to get the authorization
        :return: FedoraSearchTool
        """
        return FedoraSearchTool(base_uri, calling_class.get_auth(True))

    def clear(self):
        """
        Clear all search parameters.
        :return: void
        """
        self.fields = list()
        self.conditions = list()
        self.max_results = None
        self.offset = None
        self.order_by = None
        self.order = None

    def add_field(self, field):
        """
        Add a field to return in the search results.
        :param field: The field
        :return: void
        """
        if field not in self.fields:
            self.fields.append(field)

    def add_condition(self, field, operator, value):
        """
        Add a condition to the search
        :param field: The field to search against.
        :param operator: The operator to use in the search.
        :param value: The value to compare (operator) against the field
        :return: void
        """
        new_condition = field + operator + value
        if new_condition not in self.conditions:
            self.conditions.append(new_condition)

    def set_max_results(self, count):
        """
        Set the max results.
        :param count: Max results.
        :return: void
        """
        self.max_results = count

    def set_order_by(self, field):
        """
        Set the field to order by.
        :param field: The field.
        :return: void
        """
        self.order_by = field

    def set_order(self, order):
        """
        Set the order to use with the order_by field.
        :param order: Order
        :return: void
        TODO: Should use an enum of some sort.
        """
        self.order = order

    def set_offset(self, offset):
        """
        Set the offset.
        :param offset: The offset.
        :return: void
        """
        self.offset = offset

    def do_query(self):
        """
        Perform the search.
        :return: Response object.
        """
        parameters = {}
        for condition in self.conditions:
            if 'condition' in parameters:
                try:
                    parameters['condition'].append(condition)
                except AttributeError:
                    tmp = parameters['condition']
                    parameters['condition'] = [tmp]
                    parameters['condition'].append(condition)
            else:
                parameters['condition'] = condition

        if len(self.fields) > 0:
            parameters['fields'] = ",".join(self.fields)
        if self.max_results is not None:
            parameters['max_results'] = self.max_results
        if self.offset is not None:
            parameters['offset'] = self.offset
        if self.order_by is not None:
            parameters['order_by'] = self.order_by
        if self.order is not None:
            parameters['order'] = self.order

        return requests.get(self.baseUri + "/" + TC.FCR_SEARCH, auth=self.authz, params=parameters)
