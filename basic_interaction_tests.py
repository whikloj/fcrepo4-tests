#!/bin/env python

import TestConstants
from abstract_fedora_tests import FedoraTests, register_tests, Test
import os
import pyjq
import json
import uuid


@register_tests
class FedoraBasicIxnTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_nested"

    def createTestResource(self, type, files=None):
        """ Create a container with an expected type link type and return the URI """
        link_type = self.make_type(type)
        headers = {
            'Link': link_type
        }
        r = self.do_post(self.getBaseUri(), headers=headers, files=files)
        self.assertEqual(201, r.status_code, "Did not create container")
        location = self.get_location(r)
        self.nodes.append(location)
        r = self.do_get(location)
        self.assertEqual(200, r.status_code, "Did not get container")
        self.assertIsNotNone(r.headers['Link'], "Did not get any link headers returned")
        type_headers = FedoraTests.get_link_headers(r)
        self.assertIsNotNone(type_headers['type'], "Did not get any link headers with rel=type")
        self.assertIn(type, type_headers['type'], "Did not find link header for {}".format(type))
        return location

    @Test
    def aTestMissingResource(self):
        fake_id = str(uuid.uuid4())
        r = self.do_get(self.getFedoraBase() + "/" + fake_id)
        self.assertEqual(404, r.status_code, "Did not get expected response")

    @Test
    def testDeleteAResource(self):
        self.log("Create container")
        r = self.do_post(self.getBaseUri())
        container_location = self.get_location(r)
        self.assertEqual(201, r.status_code, "Did not get expected response")

        self.log("Check container exists")
        r = self.do_head(container_location)
        self.assertEqual(200, r.status_code, "Did not get expected response")
        r = self.do_get(container_location)
        self.assertEqual(200, r.status_code, "Did not get expected response")

        self.log("Delete the container")
        r = self.do_delete(container_location)
        self.assertEqual(204, r.status_code, "Did not get expected response")

        self.log("Check container doesn't exists")
        r = self.do_head(container_location)
        self.assertEqual(410, r.status_code, "Did not get expected response")
        r = self.do_get(container_location)
        self.assertEqual(410, r.status_code, "Did not get expected response")

        self.log("Try to put to location held by tombstone")
        r = self.do_put(container_location)
        self.assertEqual(410, r.status_code, "Did not get expected response")

        self.log("Delete the tombstone")
        r = self.do_delete(container_location + "/" + TestConstants.FCR_TOMBSTONE)
        self.assertEqual(204, r.status_code, "Did not get expected response")

        self.log("Check container doesn't exists")
        r = self.do_head(container_location)
        self.assertEqual(404, r.status_code, "Did not get expected response")
        r = self.do_get(container_location)
        self.assertEqual(404, r.status_code, "Did not get expected response")

        self.log("Try to put to location again")
        r = self.do_put(container_location)
        self.assertEqual(201, r.status_code, "Did not get expected response")


    @Test
    def testBasicContainer(self):
        self.createTestResource(TestConstants.LDP_BASIC)

    @Test
    def testDirectContainer(self):
        self.createTestResource(TestConstants.LDP_DIRECT)

    @Test
    def testIndirectContainer(self):
        self.createTestResource(TestConstants.LDP_INDIRECT)

    @Test
    def testNonRdfSource(self):
        testfiles = {'files': ('testdata.csv', 'this,is,some,data\n')}
        self.createTestResource(TestConstants.LDP_NON_RDF_SOURCE, files=testfiles)

    @Test
    def testLdpResource(self):
        """ We don't allow you to create a ldp:Resource so this returns 400 Bad Request """
        link_type = self.make_type(TestConstants.LDP_RESOURCE)
        headers = {
            'Link': link_type
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.assertEqual(400, r.status_code, "Did not get expected response")

    @Test
    def testLdpContainer(self):
        """ We don't allow you to create a ldp:Container so this returns 400 Bad Request """
        link_type = self.make_type(TestConstants.LDP_CONTAINER)
        headers = {
            'Link': link_type
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.assertEqual(400, r.status_code, "Did create container")

    @Test
    def doNestedTests(self):
        self.log("Create a container")
        r = self.createBasicContainer(self.getBaseUri())
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        location = self.get_location(r)

        self.log("Create a container in a container")
        r = self.createBasicContainer(location)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        main_child1 = self.get_location(r)

        self.log("Create binary inside a container inside a container")
        with open(os.path.join(os.getcwd(), 'resources', 'basic_image.jpg'), 'rb') as fp:
            headers = {
                'Content-type': 'image/jpeg'
            }
            data = fp.read()
            r = self.do_post(main_child1, headers=headers, body=data)
            self.assertEqual(201, r.status_code, "Did not get expected status code")
            binary_location = self.get_location(r)

        self.log("Create a second child in the top container")
        r = self.createBasicContainer(location)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        main_child2 = self.get_location(r)

        self.log("Verify containment")
        headers = {
            'Accept': TestConstants.JSONLD_MIMETYPE
        }
        r = self.do_get(location, headers=headers)
        self.assertEqual(200, r.status_code, "Can't get the container")
        body = r.content.decode('UTF-8').rstrip('\ny')
        json_body = json.loads(body)
        contained = pyjq.all('.[0]."http://www.w3.org/ns/ldp#contains"', json_body)
        expected = [
            main_child1,
            main_child2
        ]
        found = list()
        for c in contained[0]:
            child_id = pyjq.first('."@id"', c)
            found.append(child_id)
        if len(found) != len(expected):
            self.fail("Expected {0} contained resources, found {1}".format(len(expected), len(found)))
        else:
            for child_id in found:
                if child_id not in expected:
                    self.fail("Found unexpected containment relationship {0}".format(child_id))

        self.log("Delete binary")
        r = self.do_delete(binary_location)
        self.assertEqual(204, r.status_code, "Did not get expected status code")

        self.log("Verify its gone")
        r = self.do_get(binary_location)
        self.assertEqual(410, r.status_code, "Did not get expected status code")

        self.log("Delete container with a container inside it")
        r = self.do_delete(location)
        self.assertEqual(204, r.status_code, "Did not get expected status code")

        self.log("Verify both are gone")
        r = self.do_get(main_child1)
        self.assertEqual(410, r.status_code, "Did not get expected status code")
        r = self.do_get(location)
        self.assertEqual(410, r.status_code, "Did not get expected status code")

    def changeIxnModels(self, location, starting_model):
        """ This function uses a created object at {location} with starting type {starting_model}.
            The below dictionary of tuples works as such
            expected_ixn_change = {
                <Initial Model>: [
                    (<Model to change to>, <expected response status code>),
            """
        expected_ixn_change = {
            TestConstants.LDP_BASIC: [
                (TestConstants.LDP_INDIRECT, 409),
                (TestConstants.LDP_DIRECT, 409),
                (TestConstants.LDP_NON_RDF_SOURCE, 409),
                (TestConstants.LDP_RESOURCE, 400),
                (TestConstants.LDP_CONTAINER, 400)
            ],
            TestConstants.LDP_DIRECT: [
                (TestConstants.LDP_BASIC, 409),
                (TestConstants.LDP_INDIRECT, 409),
                (TestConstants.LDP_NON_RDF_SOURCE, 409),
                (TestConstants.LDP_RESOURCE, 400),
                (TestConstants.LDP_CONTAINER, 400)
            ],
            TestConstants.LDP_INDIRECT: [
                (TestConstants.LDP_BASIC, 409),
                (TestConstants.LDP_DIRECT, 409),
                (TestConstants.LDP_NON_RDF_SOURCE, 409),
                (TestConstants.LDP_RESOURCE, 400),
                (TestConstants.LDP_CONTAINER, 400)
            ],
            TestConstants.LDP_NON_RDF_SOURCE: [
                (TestConstants.LDP_BASIC, 409),
                (TestConstants.LDP_DIRECT, 409),
                (TestConstants.LDP_INDIRECT, 409),
                (TestConstants.LDP_RESOURCE, 400),
                (TestConstants.LDP_CONTAINER, 400)
            ]
        }
        for model, result in expected_ixn_change[starting_model]:
            self.log("Changing from {0} to {1} expect status {2}".format(starting_model, model, result))

            if model == TestConstants.LDP_NON_RDF_SOURCE:
                files = {'file': ('testcsvdata.csv', 'this,is,changed,data\nnow,go,away,please\n')}
            else:
                files = None

            headers = {
                'Link': self.make_type(model)
            }

            r = self.do_put(location, headers=headers, files=files)
            self.assertEqual(result, r.status_code, "Did not get expected response")

    @Test
    def testChangeIxnModel(self):
        self.log("Create a basic container")
        basic = self.createTestResource(TestConstants.LDP_BASIC)
        self.changeIxnModels(basic, TestConstants.LDP_BASIC)

        self.log("Create a direct container")
        direct = self.createTestResource(TestConstants.LDP_DIRECT)
        self.changeIxnModels(direct, TestConstants.LDP_DIRECT)

        self.log("Create a indirect container")
        indirect = self.createTestResource(TestConstants.LDP_INDIRECT)
        self.changeIxnModels(indirect, TestConstants.LDP_INDIRECT)

        self.log("Create a Non Rdf Source")
        testfiles = {'files': ('testdata.csv', 'this,is,some,data\n')}
        non_rdf = self.createTestResource(TestConstants.LDP_NON_RDF_SOURCE, files=testfiles)
        self.changeIxnModels(non_rdf, TestConstants.LDP_NON_RDF_SOURCE)
