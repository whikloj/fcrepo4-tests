#!/bin/env python
import collections
import json

import pyjq

import TestConstants
from abstract_fedora_tests import FedoraTests, register_tests, Test
import time
import rdflib
from rdflib.namespace import DC, RDF
import concurrent.futures as futures


def get_version_endpoint(uri):
    if not uri.endswith("/" + TestConstants.FCR_VERSIONS):
        uri += "/" + TestConstants.FCR_VERSIONS
    return uri


@register_tests
class FedoraVersionTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_version"

    @staticmethod
    def get_all_mementos(response):
        body = response.content.decode('UTF-8')
        mementos = [x for x in body.split('\n') if x.find("rel=\"memento\"") >= 0]
        return mementos

    @staticmethod
    def count_mementos(response):
        return len(FedoraVersionTests.get_all_mementos(response))

    def checkMementoCount(self, expected, uri, admin=None, use_link_format=True):
        if admin is None:
            admin = True
        uri = get_version_endpoint(uri)
        if use_link_format:
            rdf_type = TestConstants.LINK_FORMAT_MIMETYPE
        else:
            rdf_type = TestConstants.JSONLD_MIMETYPE
        headers = {
            'Accept': rdf_type
        }
        r = self.do_get(uri, headers=headers, admin=admin)
        self.checkResponse(200, r)
        if rdf_type == TestConstants.LINK_FORMAT_MIMETYPE:
            self.checkValue(expected, self.count_mementos(r))
        else:
            body = r.content.decode('UTF-8')
            json_body = json.loads(body)
            found_title = pyjq.all('.[] | ."@type" | .[]', json_body)
            matching = [x for x in found_title if x == expected]
            self.checkValue(expected, len(matching))

    def getNthMemento(self, uri, memento_number=1, admin=None):
        if admin is None:
            admin = True
        uri = get_version_endpoint(uri)
        headers = {
            'Accept': TestConstants.LINK_FORMAT_MIMETYPE
        }
        r = self.do_get(uri, headers=headers, admin=admin)
        self.checkResponse(TestConstants.OK, r)
        mementos = self.get_all_mementos(r)
        # Remove one to match array numbering
        memento_number -= 1
        if len(mementos) > memento_number:
            return mementos[memento_number]
        else:
            self.fail("Count not get the {} memento, only found {}".format(memento_number+1, len(mementos)))

    # Waiting on https://fedora-repository.atlassian.net/browse/FCREPO-3655
    @Test
    def doContainerVersioningTest(self):
        headers = {
            'Link': self.make_type(TestConstants.LDP_BASIC)
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.log("Create a basic container")
        self.checkResponse(TestConstants.CREATED, r)
        location = self.get_location(r)
        self.log("at " + location)

        version_endpoint = location + "/" + TestConstants.FCR_VERSIONS
        r = self.do_get(version_endpoint)
        self.checkResponse(TestConstants.OK, r)

        self.log("Create a version")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)
        memento_location = self.get_location(r)

        self.log("Get the resource content")
        headers = {
            'Accept': TestConstants.JSONLD_MIMETYPE
        }
        r = self.do_get(location, headers=headers)
        self.checkResponse(200, r)
        body = r.content.decode('UTF-8').rstrip('\n')

        new_date = FedoraTests.get_rfc_date("2000-06-01 08:21:00")

        headers = {
            'Content-Type': TestConstants.JSONLD_MIMETYPE,
            'Prefer': TestConstants.PUT_PREFER_LENIENT,
            'Memento-Datetime': new_date
        }
        self.log("Try to create a version with provided datetime (Fedora 6)")
        r = self.do_post(version_endpoint, headers=headers)
        self.checkResponse(TestConstants.BAD_REQUEST, r)

        self.log("Try to create a version with provided datetime and body (Fedora 6)")
        r = self.do_post(version_endpoint, headers=headers, body=body)
        self.checkResponse(TestConstants.BAD_REQUEST, r)

        self.log("Patch the original resource")
        sparql_body = "prefix dc: <http://purl.org/dc/elements/1.1/> " \
                      "DELETE { <> dc:title ?o . }" \
                      "INSERT { <> dc:title \"Updated title\" . }" \
                      "WHERE { <> dc:title ?o . }"
        headers = {
            "Content-Type": TestConstants.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=headers, body=sparql_body)
        self.checkResponse(TestConstants.NO_CONTENT, r)

        self.log("Try to patch the memento")
        r = self.do_patch(memento_location, headers=headers, body=sparql_body)
        self.checkResponse(TestConstants.METHOD_NOT_ALLOWED, r)

        self.log("Wait a second to change the time.")
        time.sleep(1)

        self.log("Create another version")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)

        self.log("Count mementos")
        self.checkMementoCount(2, version_endpoint)

        self.log("Try to delete a Memento")
        r = self.do_delete(memento_location)
        self.checkResponse(TestConstants.METHOD_NOT_ALLOWED, r)

        self.log("Check memento still exists.")
        r = self.do_get(memento_location)
        self.checkResponse(TestConstants.OK, r)

    @Test
    def makeVersionsInsideASecond(self):
        headers = {
            'Link': self.make_type(TestConstants.LDP_BASIC)
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.log("Create a basic container")
        self.checkResponse(TestConstants.CREATED, r)
        location = self.get_location(r)
        self.log("at " + location)

        version_endpoint = location + "/" + TestConstants.FCR_VERSIONS
        r = self.do_get(version_endpoint)
        self.checkResponse(TestConstants.OK, r)
        self.checkMementoCount(1, version_endpoint)

        time.sleep(1)

        self.log("Create multiple versions inside a second")
        with futures.ThreadPoolExecutor(max_workers=3) as ec:
            results = ec.map(self.do_post, [version_endpoint, version_endpoint, version_endpoint])
            status_codes = [r.status_code for r in results]
            counter = collections.Counter(status_codes)
            self.assertEqual(2, counter[TestConstants.CONFLICT])
            self.assertEqual(1, counter[TestConstants.CREATED])

        self.log("Count mementos")
        # Only one new memento as they are both in the same second.
        self.checkMementoCount(2, version_endpoint)
        # But multiple actual versions created
        self.checkMementoCount(2, version_endpoint, use_link_format=True)

    @Test
    def doBinaryVersioningTest(self):
        """ Test versioning with binaries and their metadata containers endpoint are synced """
        headers = {
            'Link': self.make_type(TestConstants.LDP_NON_RDF_SOURCE),
            'Content-Type': 'text/csv'
        }
        files = {'file': ('report.csv', 'some,data,to,send\nanother,row,to,send\n')}

        r = self.do_post(self.getBaseUri(), headers=headers, files=files)

        self.log("Create a NonRdfSource")
        self.checkResponse(TestConstants.CREATED, r)
        location = self.get_location(r)
        self.log("URI is {}".format(location))
        description_location = self.find_binary_description(r)

        version_endpoint = location + "/" + TestConstants.FCR_VERSIONS
        description_version_endpoint = description_location + "/" + TestConstants.FCR_VERSIONS

        self.checkMementoCount(1, location)
        self.checkMementoCount(1, description_location)

        self.log("Get version endpoint")
        r = self.do_get(version_endpoint)
        self.checkResponse(TestConstants.OK, r)

        self.log("Get description version endpoint")
        r = self.do_get(description_version_endpoint)
        self.checkResponse(TestConstants.OK, r)

        self.log("Wait for one second")
        time.sleep(1)
        self.log("Create a version")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)

        self.log("Try to create another version within a second but not at the same time")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)

        self.assertNotEqual(version_endpoint, description_version_endpoint)

        self.log("Try to create a version of the description quickly")
        r = self.do_post(description_version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)

        self.checkMementoCount(2, location)
        self.checkMementoCount(2, description_location)

        self.log("Wait one second")
        time.sleep(1)
        new_date = FedoraTests.get_rfc_date("2000-06-01 08:21:00")

        self.log("Try to create a version with provided datetime")
        headers = {
            'Content-Type': 'text/csv',
            'Memento-Datetime': new_date
        }
        r = self.do_post(version_endpoint, headers=headers, files=files)
        self.checkResponse(TestConstants.BAD_REQUEST, r)

        self.log("PUT to the original resource")
        files = {'file': ('report.csv', 'some,data,to,send\nanother,row,to,send\nevent,more,data,tosend\n')}
        headers = {
            'Content-Type': 'text/csv'
        }
        r = self.do_put(location, headers=headers, files=files)
        self.checkResponse(TestConstants.NO_CONTENT, r)

        self.log("Create a memento with a simple POST")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)
        memento_location = self.get_location(r)

        self.log("Try to GET the memento")
        r = self.do_get(memento_location)
        self.checkResponse(TestConstants.OK, r)

        self.log("Try to put to the memento")
        r = self.do_put(memento_location, headers=headers, files=files)
        self.checkResponse(TestConstants.METHOD_NOT_ALLOWED, r)

        self.log("Wait one second to change the time.")
        time.sleep(1)

        self.log("Create another version")
        r = self.do_post(version_endpoint)
        self.checkResponse(TestConstants.CREATED, r)

        self.log("Count mementos")
        self.checkMementoCount(4, version_endpoint)

        self.log("Try to DELETE the memento")
        r = self.do_delete(memento_location)
        self.checkResponse(TestConstants.METHOD_NOT_ALLOWED, r)

        self.log("Check the memento exists again")
        r = self.do_head(memento_location)
        self.checkResponse(TestConstants.OK, r)

        self.log("Validate count of mementos again")
        self.checkMementoCount(4, version_endpoint)

    @Test
    def checkBinaryVersioning(self):
        """ Test that changes to a binary are displayed on the binary description version endpoint too """
        headers = {
            'Link': self.make_type(TestConstants.LDP_NON_RDF_SOURCE),
            'Content-Type': 'text/csv'
        }
        files = {'file': ('report.csv', 'some,data,to,send\nanother,row,to,send\n')}

        self.log("Create a NonRdfSource")
        r = self.do_post(self.getBaseUri(), headers=headers, files=files)
        self.checkResponse(201, r)
        location = self.get_location(r)
        description_location = self.find_binary_description(r)

        binary_versions = location + "/" + TestConstants.FCR_VERSIONS
        metadata_versions = description_location + "/" + TestConstants.FCR_VERSIONS

        link_headers = {
            'Accept': TestConstants.LINK_FORMAT_MIMETYPE
        }

        self.log("Count Mementos of binary")
        r = self.do_get(binary_versions, headers=link_headers)
        self.checkResponse(200, r)
        self.checkValue(1, self.count_mementos(r))

        self.log("Count Mementos of binary description")
        r = self.do_get(metadata_versions, headers=link_headers)
        self.checkResponse(200, r)
        self.checkValue(1, self.count_mementos(r))

        self.log("Wait a second")
        time.sleep(1)

        self.log("Create version of binary from existing")
        r = self.do_post(binary_versions)
        self.checkResponse(201, r)

        self.log("Count Mementos of binary")
        self.checkMementoCount(2, binary_versions)

        self.log("Count Mementos of binary description")
        self.checkMementoCount(2, metadata_versions)

        self.log("Wait a second")
        time.sleep(1)

        self.log("Create version of binary metadata from existing")
        r = self.do_post(metadata_versions)
        self.checkResponse(201, r)

        self.log("Count Mementos of binary")
        self.checkMementoCount(3, binary_versions)

        self.log("Count Mementos of binary description")
        self.checkMementoCount(3, metadata_versions)

    @Test
    def createBinaryVersionsWithTimeOrBody(self):
        """ Test we can no longer provide a version datetime or a version body """
        headers = {
            'Link': self.make_type(TestConstants.LDP_NON_RDF_SOURCE),
            'Content-Type': 'text/csv'
        }
        files = {'file': ('report.csv', 'some,data,to,send\nanother,row,to,send\n')}

        self.log("Create a NonRdfSource")
        r = self.do_post(self.getBaseUri(), headers=headers, files=files)
        self.checkResponse(201, r)
        location = self.get_location(r)
        description_location = self.find_binary_description(r)

        r = self.do_get(description_location)
        new_body = "@prefix dc: <{0}> .\n".format(TestConstants.DC_NS) + \
            r.text[0:-2] + ";\n dc:title \"New title\" .\n".format(TestConstants.DC_NS)

        version_endpoint = location + "/" + TestConstants.FCR_VERSIONS
        description_version_endpoint = description_location + "/" + TestConstants.FCR_VERSIONS

        self.log("Check we have a single mementos of binary and description (auto-versioning)")
        self.checkMementoCount(1, version_endpoint)
        self.checkMementoCount(1, description_version_endpoint)

        the_date = FedoraTests.get_rfc_date('2019-05-21 18:30:00')
        files = {'file': ('report.csv', 'some,data,to,send\nanother,row,to,send\nevent,more,data,tosend\n')}
        headers = {
            'Content-Type': 'text/csv',
            'Memento-Datetime': the_date
        }

        self.log("Can't make version for {0} of binary with a body".format(the_date))
        r = self.do_post(version_endpoint, headers=headers, files=files)
        self.checkResponse(TestConstants.BAD_REQUEST, r)

        self.log("Check we haven't made a memento of the binary")
        self.checkMementoCount(1, version_endpoint)
        self.log("Check we haven't made a memento of the description")
        self.checkMementoCount(1, description_version_endpoint)

        headers = {
            'Content-type': TestConstants.TURTLE_MIMETYPE,
            'Memento-Datetime': the_date,
            'Prefer': TestConstants.PUT_PREFER_LENIENT
        }

        self.log("Can't make version for {0} of binary description with a body".format(the_date))
        r = self.do_post(description_version_endpoint, headers=headers, body=new_body)
        self.checkResponse(TestConstants.BAD_REQUEST, r)

        self.log("Count binary mementos")
        self.checkMementoCount(1, version_endpoint)

        self.log("Count binary description mementos")
        self.checkMementoCount(1, description_version_endpoint)

    @Test
    def testMementoAreAccessibleAfterDelete(self):
        """ Test mementos are still accessible when a resource is deleted but not purged. """
        r = self.do_post()
        self.checkResponse(TestConstants.CREATED, r)
        uri = self.get_location(r)

        self.verifyGet(uri)

        r = self.do_post(uri + "/" + TestConstants.FCR_VERSIONS)
        self.checkResponse(TestConstants.CREATED, r)
        memento = self.get_location(r)
        self.log("Wait a second or the memento and the delete will occur in the same second")
        time.sleep(1)

        self.verifyGet(memento)

        r = self.do_delete(uri)
        self.checkResponse(TestConstants.NO_CONTENT, r)

        self.verifyGone(uri)
        # TimeMaps and Mementos are accessible after the resource is deleted (but not purged) as of 6.5.0
        self.verifyGet(uri + "/" + TestConstants.FCR_VERSIONS)
        self.verifyGet(memento)

    @Test
    def testBinaryDescription(self):
        """ Test checking past versions of binary descriptions """
        headers = {
            'Content-type': 'text/plain'
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body="Some example text")
        self.checkResponse(TestConstants.CREATED, r)
        location = self.get_location(r)
        description_uri = location + "/" + TestConstants.FCR_METADATA
        test_type = "http://example.org/customType"

        headers = {
            'Content-type': "application/sparql-update"
        }
        update_string = "INSERT { <> <" + TestConstants.DC_TITLE + "> \"Original\" ." \
            " <> <" + TestConstants.RDF_TYPE + "> <" + test_type + "> } WHERE { }"

        r1 = self.do_patch(description_uri, update_string, headers=headers)
        self.checkResponse(TestConstants.NO_CONTENT, r1)

        r2 = self.do_post(description_uri + "/" + TestConstants.FCR_VERSIONS)
        self.checkResponse(TestConstants.CREATED, r2)
        memento = self.get_location(r2)

        changed_string = "INSERT { <" + location + "> <" + TestConstants.DC_TITLE + "> \"Updated\". } WHERE { }"
        r3 = self.do_patch(description_uri, changed_string, headers=headers)
        self.checkResponse(TestConstants.NO_CONTENT, r3)

        r4 = self.do_get(memento, headers={'Accept': 'application/n-triples'})
        self.checkResponse(TestConstants.OK, r4)
        graph = rdflib.Graph()
        graph.parse(data=r4.content, format="nt")

        subject_uri = rdflib.URIRef(location)

        # Have to use assertTrue( triple NOT IN graph) or it throws an exception.
        self.assertTrue("Property added to original before versioning must appear",
                        (subject_uri, DC.title, rdflib.Literal("Original")) in graph)
        self.assertTrue("Property added after memento created must not appear",
                        (subject_uri, DC.title, rdflib.Literal("Updated")) not in graph)
        self.assertTrue("Memento type should not be visible",
                        (subject_uri, RDF.type, rdflib.URIRef(TestConstants.MEM_MEMENTO)) not in graph)
        self.assertTrue("Must have binary type",
                        (subject_uri, RDF.type, rdflib.URIRef(TestConstants.FEDORA_BINARY)) in graph)
        self.assertTrue("Must have custom type",
                        (subject_uri, RDF.type, rdflib.URIRef(test_type)) in graph)
