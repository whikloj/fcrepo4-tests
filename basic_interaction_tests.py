#!/bin/env python
import random
import shutil
import string
import tempfile
import time

import TestConstants as TC
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
        self.log("Create the resource")
        r = self.do_post(self.getBaseUri(), headers=headers, files=files)
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)
        self.nodes.append(location)
        self.log("GET the resource")
        r = self.do_get(location)
        self.checkResponse(TC.OK, r)
        self.assertHeaderExists(r, 'Link')
        type_headers = FedoraTests.get_link_headers(r)
        self.assertIsNotNone(type_headers['type'], "Did not get any link headers with rel=type")
        self.assertIn(type, type_headers['type'], "Did not find link header for {}".format(type))
        return location

    def getEtag(self, uri):
        """ Get the eTag header for a specified URI. """
        return self.getHeader(uri, "ETag").strip()

    def getStateToken(self, uri):
        """ Get the X-State-Token header for a specified URI. """
        return self.getHeader(uri, "X-State-Token").strip()

    def duplicateImage(self):
        """ Copy the test image to a location """
        new_file = os.path.join(tempfile.gettempdir(), 'temp_image.jpeg')
        shutil.copyfile(self.getImagePath(), new_file)
        return new_file

    @Test
    def testMissingResource(self):
        """ Test we get a 404 for a non-existant resource """
        fake_id = str(uuid.uuid4())
        r = self.do_get(self.getFedoraBase() + "/" + fake_id)
        self.assertEqual(404, r.status_code, "Did not get expected response")

    @Test
    def testDeleteAResource(self):
        """ Test that we can reuse an atomic resource URL once it is purged """
        self.log("Create container")
        r = self.do_post(self.getBaseUri())
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)

        self.log("Check container exists")
        r = self.do_head(container_location)
        self.checkResponse(TC.OK, r)
        r = self.do_get(container_location)
        self.checkResponse(TC.OK, r)

        self.log("Delete the container")
        r = self.do_delete(container_location)
        self.checkResponse(TC.NO_CONTENT, r)

        self.log("Check container doesn't exists")
        r = self.do_head(container_location)
        self.checkResponse(TC.GONE, r)
        r = self.do_get(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to put to location held by tombstone")
        r = self.do_put(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Delete the tombstone")
        r = self.do_delete(container_location + "/" + TC.FCR_TOMBSTONE)
        self.checkResponse(TC.NO_CONTENT, r)

        self.log("Check container doesn't exists")
        r = self.do_head(container_location)
        self.checkResponse(TC.NOT_FOUND, r)
        r = self.do_get(container_location)
        self.checkResponse(TC.NOT_FOUND, r)

        self.log("Try to put to location again")
        r = self.do_put(container_location)
        self.checkResponse(TC.CREATED, r)

    @Test
    def testBasicContainer(self):
        """ Test creating a basic container """
        self.createTestResource(TC.LDP_BASIC)

    @Test
    def testDirectContainer(self):
        """ Test creating a direct container """
        self.createTestResource(TC.LDP_DIRECT)

    @Test
    def testIndirectContainer(self):
        """ Test creating an indirect container """
        self.createTestResource(TC.LDP_INDIRECT)

    @Test
    def testNonRdfSource(self):
        """ Test creating a binary """
        testfiles = {'files': ('testdata.csv', 'this,is,some,data\n')}
        self.createTestResource(TC.LDP_NON_RDF_SOURCE, files=testfiles)

    @Test
    def testLdpResource(self):
        """ We don't allow you to create a ldp:Resource so this returns 400 Bad Request """
        link_type = self.make_type(TC.LDP_RESOURCE)
        headers = {
            'Link': link_type
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.checkResponse(TC.BAD_REQUEST, r)

    @Test
    def testLdpContainer(self):
        """ We don't allow you to create a ldp:Container so this returns 400 Bad Request """
        link_type = self.make_type(TC.LDP_CONTAINER)
        headers = {
            'Link': link_type
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.checkResponse(TC.BAD_REQUEST, r)

    @Test
    def doNestedTests(self):
        """ Test creating child objects and removing them """
        self.log("Create a container")
        r = self.createBasicContainer(self.getBaseUri())
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        self.log("Create a container in a container")
        r = self.createBasicContainer(location)
        self.checkResponse(TC.CREATED, r)
        main_child1 = self.get_location(r)

        self.log("Create binary inside a container inside a container")
        with open(os.path.join(os.getcwd(), 'resources', 'basic_image.jpg'), 'rb') as fp:
            headers = {
                'Content-type': 'image/jpeg'
            }
            data = fp.read()
            r = self.do_post(main_child1, headers=headers, body=data)
            self.checkResponse(TC.CREATED, r)
            binary_location = self.get_location(r)

        self.log("Create a second child in the top container")
        r = self.createBasicContainer(location)
        self.checkResponse(TC.CREATED, r)
        main_child2 = self.get_location(r)

        self.log("Verify containment")
        headers = {
            'Accept': TC.JSONLD_MIMETYPE
        }
        r = self.do_get(location, headers=headers)
        self.checkResponse(TC.OK, r)
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
        self.checkResponse(TC.NO_CONTENT, r)

        self.log("Verify its gone")
        r = self.do_get(binary_location)
        self.checkResponse(TC.GONE, r)

        self.log("Delete container with a container inside it")
        r = self.do_delete(location)
        self.checkResponse(TC.NO_CONTENT, r)

        self.log("Verify both are gone")
        r = self.do_get(main_child1)
        self.checkResponse(TC.GONE, r)
        r = self.do_get(location)
        self.checkResponse(TC.GONE, r)

    @Test
    def testPurgeContainer(self):
        """ Test create, delete and purge a container """
        r = self.do_post()
        self.checkResponse(TC.CREATED, r)
        uri = self.get_location(r)

        self.verifyGet(uri)

        r = self.do_post(uri)
        self.checkResponse(TC.CREATED, r)
        childUri = self.get_location(r)

        r = self.do_delete(childUri)
        self.checkResponse(TC.NO_CONTENT, r)

        r = self.do_get(childUri)
        self.checkResponse(TC.GONE, r)

        r = self.do_delete(childUri + "/" + TC.FCR_TOMBSTONE)
        self.checkResponse(TC.NO_CONTENT, r)

        r = self.do_get(childUri)
        self.checkResponse(TC.NOT_FOUND, r)

        r = self.do_put(childUri)
        self.checkResponse(TC.CREATED, r)

    @Test
    def testPurgeBinary(self):
        """ Test create, delete and purge a binary """
        headers = {
            'Link': "<{}>; rel=\"type\"".format(TC.LDP_NON_RDF_SOURCE)
        }
        r = self.do_post(headers=headers, body="some text")
        self.checkResponse(TC.CREATED, r)
        childUri = self.get_location(r)

        self.verifyGet(childUri)

        r = self.do_delete(childUri)
        self.checkResponse(TC.NO_CONTENT, r)

        r = self.do_get(childUri)
        self.checkResponse(TC.GONE, r)

        r = self.do_delete(childUri + "/" + TC.FCR_TOMBSTONE)
        self.checkResponse(TC.NO_CONTENT, r)

        r = self.do_get(childUri)
        self.checkResponse(TC.NOT_FOUND, r)

        r = self.do_put(childUri)
        self.checkResponse(TC.CREATED, r)

    def changeIxnModels(self, location, starting_model):
        """ This function uses a created object at {location} with starting type {starting_model}.
            The below dictionary of tuples works as such
            expected_ixn_change = {
                <Initial Model>: [
                    (<Model to change to>, <expected response status code>),
            """
        expected_ixn_change = {
            TC.LDP_BASIC: [
                (TC.LDP_INDIRECT, 409),
                (TC.LDP_DIRECT, 409),
                (TC.LDP_NON_RDF_SOURCE, 409),
                (TC.LDP_RESOURCE, 400),
                (TC.LDP_CONTAINER, 400)
            ],
            TC.LDP_DIRECT: [
                (TC.LDP_BASIC, 409),
                (TC.LDP_INDIRECT, 409),
                (TC.LDP_NON_RDF_SOURCE, 409),
                (TC.LDP_RESOURCE, 400),
                (TC.LDP_CONTAINER, 400)
            ],
            TC.LDP_INDIRECT: [
                (TC.LDP_BASIC, 409),
                (TC.LDP_DIRECT, 409),
                (TC.LDP_NON_RDF_SOURCE, 409),
                (TC.LDP_RESOURCE, 400),
                (TC.LDP_CONTAINER, 400)
            ],
            TC.LDP_NON_RDF_SOURCE: [
                (TC.LDP_BASIC, 409),
                (TC.LDP_DIRECT, 409),
                (TC.LDP_INDIRECT, 409),
                (TC.LDP_RESOURCE, 400),
                (TC.LDP_CONTAINER, 400)
            ]
        }
        for model, result in expected_ixn_change[starting_model]:
            self.log("Changing from {0} to {1} expect status {2}".format(starting_model, model, result))

            if model == TC.LDP_NON_RDF_SOURCE:
                files = {'file': ('testcsvdata.csv', 'this,is,changed,data\nnow,go,away,please\n')}
            else:
                files = None

            headers = {
                'Link': self.make_type(model)
            }

            r = self.do_put(location, headers=headers, files=files)
            self.checkResponse(result, r)

    @Test
    def testChangeIxnModel(self):
        """ Test responses when trying to change interaction models """
        self.log("Create a basic container")
        basic = self.createTestResource(TC.LDP_BASIC)
        self.changeIxnModels(basic, TC.LDP_BASIC)

        self.log("Create a direct container")
        direct = self.createTestResource(TC.LDP_DIRECT)
        self.changeIxnModels(direct, TC.LDP_DIRECT)

        self.log("Create a indirect container")
        indirect = self.createTestResource(TC.LDP_INDIRECT)
        self.changeIxnModels(indirect, TC.LDP_INDIRECT)

        self.log("Create a Non Rdf Source")
        testfiles = {'files': ('testdata.csv', 'this,is,some,data\n')}
        non_rdf = self.createTestResource(TC.LDP_NON_RDF_SOURCE, files=testfiles)
        self.changeIxnModels(non_rdf, TC.LDP_NON_RDF_SOURCE)

    @Test
    def testBinaryTriples(self):
        """ Test you can create a binary with some expected headers """
        self.log("Create binary with expected properties")
        headers = {
            'Content-type': 'text/plain',
            'Content-Disposition': 'attachment; filename="mytestfile.txt"'
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body="some sample text")
        self.checkResponse(TC.CREATED, r)

    @Test
    def testChecksum(self):
        """ Test that interaction of state tokens and eTags
        TODO: This test flaps a bit """
        self.log("Create parent resource")
        r = self.do_post(self.getBaseUri())
        self.checkResponse(TC.CREATED, r)
        parent_uri = self.get_location(r)

        first_etag = self.getEtag(parent_uri)
        first_state_token = self.getStateToken(parent_uri)
        self.log(f"First eTag of parent is {first_etag} and state token is {first_state_token}")
        time.sleep(0.5)
        self.log("Add child resource to parent")
        r = self.do_post(parent_uri)
        self.checkResponse(TC.CREATED, r)

        second_etag = self.getEtag(parent_uri)
        second_state_token = self.getStateToken(parent_uri)
        self.log(f"Second eTag of parent is {second_etag} and state token is {second_state_token}")

        self.assertNotEqual(first_etag, second_etag, "First and second state etags should not match")
        self.assertEqual(first_state_token, second_state_token, "First and second state tokens should match")
        
        self.log("Add 30 child resources to parent")
        for i in range(1, 30):
            r = self.do_post(parent_uri, {'Slug': 'child_' + str(i)})
            self.checkResponse(TC.CREATED, r)

        third_etag = self.getEtag(parent_uri)
        third_state_token = self.getStateToken(parent_uri)
        if third_etag == second_etag:
            start = time.perf_counter()
            self.log("Waiting up to 2 seconds to account for H2 delay on eTags")
            while second_etag == third_etag and time.perf_counter() - start < 2:
                time.sleep(.3)
                third_etag = self.getEtag(parent_uri)
                third_state_token = self.getStateToken(parent_uri)
        self.log(f"Third eTag of parent is {third_etag} and state token is {third_state_token}")
        self.assertNotEqual(first_etag, third_etag, "First and third state etag should not match")
        self.assertNotEqual(second_etag, third_etag, "Second and third state etag should not match")

        self.assertEqual(first_state_token, third_state_token, "First and third state tokens should match")
        self.assertEqual(second_state_token, third_state_token, "Second and third state tokens should match")

        r = self.do_patch(parent_uri, headers={'Content-type': TC.SPARQL_UPDATE_MIMETYPE},
                          body="INSERT {<> <" + TC.DC_TITLE + "> 'Some title'. } WHERE {}")
        self.checkResponse(TC.NO_CONTENT, r)

        fourth_etag = self.getEtag(parent_uri)
        fourth_state_token = self.getStateToken(parent_uri)
        self.log(f"Fourth eTag of parent is {fourth_etag} and state token is {fourth_state_token}")
        self.assertNotEqual(third_etag, fourth_etag, "Third and fourth state etag should match")
        self.assertNotEqual(third_state_token, fourth_state_token, "Third and fourth state tokens should not match")

    # @Test # These tests require Fedora to allow the paths, might require more thought.
    def testExternalContentProxyLocal(self):
        self.log("Create external content to local resource")
        image_path = self.duplicateImage()
        external_headers = {
            "Link": "<file://{}>; rel =\"http://fedora.info/definitions/fcrepo#ExternalContent\"; "
            "handling=\"proxy\"; type=\"image/jpeg\"".format(image_path)
        }
        r = self.do_post(headers=external_headers)
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)
        r = self.do_get(location)
        self.checkResponse(TC.OK, r)
        self.assertHeaderExists(r, "Content-type", "image/jpeg")
        self.log("Delete the local file")
        os.unlink(image_path)
        r = self.do_get(location)
        self.checkResponse(TC.SERVER_ERROR, r)

    # @Test # These tests require Fedora to allow the paths, might require more thought.
    def testExternalContentProxyCopy(self):
        self.log("Create external content to local resource")
        image_path = self.duplicateImage()
        external_headers = {
            "Link": "<file://{}>; rel =\"http://fedora.info/definitions/fcrepo#ExternalContent\"; "
            "handling=\"copy\"; type=\"image/jpeg\"".format(image_path)
        }
        r = self.do_post(headers=external_headers)
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)
        r = self.do_get(location)
        self.checkResponse(TC.OK, r)
        self.assertHeaderExists(r, "Content-type", "image/jpeg")
        self.log("Delete the local file")
        os.unlink(image_path)
        r = self.do_get(location)
        self.checkResponse(TC.OK, r)

    # @Test # These tests require Fedora to allow the paths, might require more thought.
    def testExternalContentHttpProxy(self):
        self.log("Create a resource")
        with open(self.getImagePath(), 'rb') as fp:
            data = fp.read()
            r = self.do_post(headers={
                "Content-type": "image/jpeg"
            }, body=data)
            self.checkResponse(TC.CREATED, r)
            external_location = self.get_location(r)
        self.log("Create external content to http resource")
        external_headers = {
            "Link": "<{}>; rel =\"http://fedora.info/definitions/fcrepo#ExternalContent\"; "
                    "handling=\"proxy\"; type=\"image/jpeg\"".format(external_location)
        }
        r = self.do_post(headers=external_headers)
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)
        r = self.do_get(location)
        self.checkResponse(TC.OK, r)
        self.log("Delete the local file")

    @Test
    def testDeleteAndPutOverTombstoneRdf(self):
        """ Test you need the header for PUT over a RDFSource tombstone """
        self.log("Create resource")
        r = self.do_post()
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        self.log("Delete resource")
        r = self.do_delete(location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over tombstone")
        r = self.do_put(location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over tombstone, with header")
        r = self.do_put(location, headers={
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CREATED, r)

    @Test
    def testDeleteAndPutOverTombstoneNonRdf(self):
        """ Test you need the header for PUT over a NonRDFSource tombstone """
        self.log("Create NonRdf resource")
        r = self.do_post(headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain'
        }, body="Hello World!")
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        self.log("Delete resource")
        r = self.do_delete(location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over tombstone")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain'
        }, body="New body")
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over tombstone, with header")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain',
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        }, body="New body")
        self.checkResponse(TC.CREATED, r)

    @Test
    def testDeleteAndPutOverTombstoneWrongTypeRdf(self):
        """ Test you can't PUT a NonRDFSource over a tombstone for a RDFSource """
        self.log("Create resource RDF")
        r = self.do_post()
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        self.log("Delete resource")
        r = self.do_delete(location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT NonRdfSource over tombstone")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain'
        }, body="Hello World!")
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over NonRdfSource tombstone, with header")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain',
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CONFLICT, r)

    @Test
    def testDeleteAndPutOverTombstoneWrongTypeNonRdf(self):
        """ Test you can't PUT a RDFSource over a tombstone for a NonRDFSource """
        self.log("Create resource NonRDF")
        r = self.do_post(headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain'
        }, body="Hello World!")
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        self.log("Delete resource")
        r = self.do_delete(location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT RdfSource over tombstone")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_BASIC),
        })
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over RdfSource tombstone, with header")
        r = self.do_put(location, headers={
            'Link': self.make_type(TC.LDP_BASIC),
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CONFLICT, r)

    @Test
    def testRangeRequests(self):
        """ Test that we support RFC 7233 range requests """
        self.log("Create a NonRDFResource")
        r = self.do_post(headers={
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE),
            'Content-type': 'text/plain'
        }, body=''.join(random.choices(string.ascii_lowercase, k=100)))
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)
        length = self.getHeader(location, 'Content-Length')
        if length is not None:
            half_length = int(int(length) / 2)
            one_longer = int(length) + 1

            self.log("Perform request for first half of the range")
            r = self.do_get(location, headers={
                'Range': 'bytes=0-{0}'.format(half_length)
            })
            self.checkResponse(TC.PARTIAL_CONTENT, r)
            range = r.headers['Content-Range']
            if range:
                self.assertEqual('bytes 0-{0}/{1}'.format(half_length, length), range)
            else:
                self.fail("No Content-Range header found")

            self.log("Perform request for range slightly longer than the content")
            r = self.do_get(location, headers={
                'Range': 'bytes=0-{0}'.format(one_longer)
            })
            self.checkResponse(TC.PARTIAL_CONTENT, r)
            range = r.headers['Content-Range']
            if range:
                self.assertEqual('bytes 0-{0}/{1}'.format(int(length) - 1, length), range)
            else:
                self.fail("No Content-Range header found")

            self.log("Perform request for range of the content length")
            r = self.do_get(location, headers={
                'Range': 'bytes=0-{0}'.format(length)
            })
            self.checkResponse(TC.PARTIAL_CONTENT, r)
            range = r.headers['Content-Range']
            if range:
                self.assertEqual('bytes 0-{0}/{1}'.format(int(length) -1, length), range)
            else:
                self.fail("No Content-Range header found")
