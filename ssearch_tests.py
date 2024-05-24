#!/bin/env python
import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test
from FedoraSearchTool import FedoraSearchTool
import pyjq
import json


@register_tests
class FedoraSimpleSearchTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_search"

    search = None

    def createSomeResources(self, base=None, count=10):
        """
        Create some resources and track the URIs
        :param base: The base uri to POST to.
        :param count: The number of resources to create.
        :return: List of created resource URIs.
        """
        resource_ids = list()
        if base is None:
            base = self.getBaseUri()
        for x in range(0, count):
            r = self.do_post(base)
            location = self.get_location(r)
            resource_ids.append(location)
        return resource_ids

    def getSearch(self):
        """
        Get a FedoraSearchTool instance.
        :return: The FedoraSearchTool.
        """
        if self.search is None:
            self.search = FedoraSearchTool.create(self.getFedoraBase(), self)
        return self.search

    @Test
    def testSearchAll(self):
        """ Test that a search returns all resources created """
        max_results = 20
        offset = 0
        items = self.createSomeResources(count=5)
        found = []
        search = self.getSearch()
        search.add_condition("fedora_id", "=", "*")
        while len(found) < len(items) and offset < 5:
            search.set_max_results(max_results)
            search.set_offset((offset * max_results))
            r = search.do_query()
            self.checkResponse(200, r)
            body = r.content.decode('UTF-8')
            body_json = json.loads(body)
            for item in items:
                if pyjq.first('."items" | reduce .[] as $item (false; if $item."fedora_id" == "{}"'
                              ' then true else . end)'.format(item), body_json):
                    # Found the item so add it to the list.
                    found.append(item)
            offset += 1
        if len(found) < len(items):
            self.fail("Did not find all created ids.")

    @Test
    def testWithBadParameter(self):
        """ Test that a bad parameter returns a 400 status """
        search = self.getSearch()
        search.add_condition("myField", "=", "*")
        r = search.do_query()
        self.checkResponse(TC.BAD_REQUEST, r)
