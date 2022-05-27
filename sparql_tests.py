#!/bin/env python

import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test
import os
import json
import pyjq


@register_tests
class FedoraSparqlTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_sparql"

    TITLE_SPARQL = "prefix dc: <http://purl.org/dc/elements/1.1/>" \
                   "INSERT { <> dc:title \"First title\". } WHERE {}"

    UPDATE_SPARQL = "prefix dc: <http://purl.org/dc/elements/1.1/> " \
                    "DELETE { <> dc:title ?o . } INSERT { <> dc:title \"Updated title\" .} WHERE { <> dc:title ?o . }"

    @Test
    def doSparqlContainerTest(self):
        self.log("Create container")
        headers = {
            'Content-type': 'text/turtle'
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body=TC.OBJECT_TTL)
        self.assertEqual(201, r.status_code, "Did not create container")
        location = self.get_location(r)

        self.log("Set dc:title with SPARQL")
        patch_headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=patch_headers, body=self.TITLE_SPARQL)
        self.assertEqual(204, r.status_code, "Did not get expected result")
        self.assertTitleExists("First title", location)

        self.log("Update dc:title with SPARQL")
        r = self.do_patch(location, headers=patch_headers, body=self.UPDATE_SPARQL)
        self.assertEqual(204, r.status_code, "Did not get expected results")
        self.assertTitleExists("Updated title", location)

    @Test
    def doSparqlBinaryTest(self):
        self.log("Create a binary")
        headers = {
            'Content-type': 'image/jpeg'
        }
        with open(os.path.join(os.getcwd(), 'resources', 'basic_image.jpg'), 'rb') as fp:
            data = fp.read()
            r = self.do_post(self.getBaseUri(), headers=headers, body=data)
            self.assertEqual(201, r.status_code, "Did not get expected response")
            description = self.find_binary_description(r)

        self.log("Set dc:title with SPARQL")
        patch_headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(description, headers=patch_headers, body=self.TITLE_SPARQL)
        self.assertEqual(204, r.status_code, "Did not get expected result")
        self.assertTitleExists("First title", description)

        self.log("Update dc:title with SPARQL")
        r = self.do_patch(description, headers=patch_headers, body=self.UPDATE_SPARQL)
        self.assertEqual(204, r.status_code, "Did not get expected results")
        self.assertTitleExists("Updated title", description)

    @Test
    def doUnicodeSparql(self):
        self.log("Create a container")
        r = self.do_post(self.getBaseUri())
        self.assertEqual(201, r.status_code, "Did not get expected response code")
        location = self.get_location(r)

        sparql = "PREFIX dc: <http://purl.org/dc/elements/1.1/> " \
                 "INSERT { <> dc:title \"Die von Blumenbach gegründete anthropologische Sammlung der Universität\" . }" \
                 " WHERE {}".encode('UTF-8')

        self.log("Patching with unicode")
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=headers, body=sparql)
        self.assertEqual(204, r.status_code, "Did not get expected response code")
        self.assertTitleExists("Die von Blumenbach gegründete anthropologische Sammlung der Universität", location)

    @Test
    def doAddType(self):
        self.log("Create a container")
        r = self.do_post(self.getBaseUri())
        self.assertEqual(201, r.status_code, "Did not get expected response code")
        location = self.get_location(r)

        sparql = "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> " \
                 "PREFIX ldp: <http://www.w3.org/ns/ldp#> " \
                 "PREFIX example: <http://www.example.org/ns#> " \
                 "INSERT DATA { <> rdf:type example:type }"
        self.log("Patching with our own type")
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=headers, body=sparql)
        self.assertEqual(204, r.status_code, "Did not get expected response code")
        self.assertTypeExists("http://www.example.org/ns#type", location)

    @Test
    def doAddRestrictedType(self):
        self.log("Create a container")
        r = self.do_post(self.getBaseUri())
        self.assertEqual(201, r.status_code, "Did not get expected response code")
        location = self.get_location(r)

        sparql = "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> " \
                 "PREFIX ldp: <http://www.w3.org/ns/ldp#> " \
                 "PREFIX example: <http://www.example.org/ns#> " \
                 "INSERT DATA {{ <> rdf:type <{0}> }}".format(TC.LDP_DIRECT)
        self.log("Patching with our own type")
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=headers, body=sparql)
        self.assertEqual(409, r.status_code, "Did not get expected response code")

    @Test
    def doInboundReferenceContainer(self):
        reference = "http://awoods.com/pointer"
        self.log("Create a container")
        r = self.do_post(self.getBaseUri())
        self.checkResponse(201, r)
        location = self.get_location(r)
        self.log("Create a RDF container with a reference to the first container.")
        rdf = "<> <{}> <{}> .".format(reference, location)
        headers = {
            'Content-type': TC.TURTLE_MIMETYPE,
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body=rdf)
        self.checkResponse(201, r)
        second_location = self.get_location(r)
        self.log("Get first container")
        r = self.do_get(location)
        self.checkResponse(200, r)
        self.log("Get second container")
        r = self.do_get(second_location)
        self.checkResponse(200, r)
        self.log("Get first container with Inbound References")
        headers = {
            'Prefer': "return=representation; include=\"{}\"".format(TC.INBOUND_REFERENCE),
            'Accept': TC.JSONLD_MIMETYPE
        }
        r = self.do_get(location, headers=headers)
        self.checkResponse(200, r)
        body = r.content.decode('UTF-8')
        json_body = json.loads(body)
        result = pyjq.all('.[] | select(."@id" == "{}") | ."{}" | .[0]."@id"'.format(second_location, reference), json_body)
        self.assertEqual(location, result[0])

    @Test
    def doInboundReferenceBinary(self):
        reference = "http://awoods.com/pointer"
        self.log("Create a binary")
        headers = {
            'Content-type': 'text/plain'
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body="Some test text")
        self.checkResponse(201, r)
        location = self.get_location(r)
        location_metadata = location + "/" + TC.FCR_METADATA
        self.log("Create a RDF container with a reference to the binary.")
        rdf = "<> <{}> <{}> .".format(reference, location)
        headers = {
            'Content-type': TC.TURTLE_MIMETYPE,
        }
        r = self.do_post(self.getBaseUri(), headers=headers, body=rdf)
        self.checkResponse(201, r)
        second_location = self.get_location(r)
        self.log("Get binary")
        r = self.do_get(location)
        self.checkResponse(200, r)
        self.log("Get binary description")
        r = self.do_get(location_metadata)
        self.checkResponse(200, r)
        self.log("Get first container")
        r = self.do_get(second_location)
        self.checkResponse(200, r)
        self.log("Get binary description with Inbound References")
        headers = {
            'Prefer': "return=representation; include=\"{}\"".format(TC.INBOUND_REFERENCE),
            'Accept': TC.JSONLD_MIMETYPE
        }
        r = self.do_get(location_metadata, headers=headers)
        self.checkResponse(200, r)
        body = r.content.decode('UTF-8')
        json_body = json.loads(body)
        result = pyjq.all('.[] | select(."@id" == "{}") | ."{}" | .[0]."@id"'.format(second_location, reference),
                          json_body)
        self.assertEqual(location, result[0])

    @Test
    def testInboundReferenceToSelf(self):
        reference = "http://awoods.com/pointsTo"
        r = self.do_post(self.getBaseUri())
        self.checkResponse(TC.CREATED, r)
        location = self.get_location(r)

        body = "INSERT {{ <> <{}> <{}> }} WHERE {{}}".format(reference, location)
        headers = {
            "Content-type": TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(location, headers=headers, body=body)
        self.checkResponse(TC.NO_CONTENT, r)

        headers = {
            'Prefer': "return=representation; include=\"{}\"".format(TC.INBOUND_REFERENCE),
            'Accept': TC.JSONLD_MIMETYPE
        }
        r = self.do_get(location, headers=headers)
        self.checkResponse(200, r)
        body = r.content.decode('UTF-8')
        json_body = json.loads(body)
        result = pyjq.all('.[] | select(."@id" == "{}") | ."{}" '.format(location, reference), json_body)
        self.assertEqual(1, len(result))
