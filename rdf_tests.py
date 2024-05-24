#!/bin/env python
import time

import rdflib.parser

import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test


@register_tests
class FedoraRdfTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_rdf"

    RDF_VARIANTS = [
        "text/turtle;charset=utf-8",
        "application/rdf+xml;charset=utf-8",
        "application/ld+json;charset=utf-8",
        "application/n-triples;charset=utf-8",
        "text/n3;charset=utf-8"
    ]

    @Test
    def testRdfSerialization(self):
        """ Test GETting RDF in supported formats """
        self.log("Put new resource.")
        r = self.createBasicContainer(self.getBaseUri())
        self.assertEqual(201, r.status_code, "Did not create new object")
        location = self.get_location(r)

        self.log("Check for correct title.")
        self.assertTitleExists("An Object", location)

        self.log("PUT to update title.")
        n_triples = "<{0}> <{1}> \"Updated Title\" .".format(location, TC.DC_TITLE)
        headers = {
            "Content-type": "application/n-triples",
            "Prefer": TC.PUT_PREFER_LENIENT
        }
        r = self.do_put(location, headers=headers, body=n_triples)
        self.assertEqual(204, r.status_code, "Did not update the resource")

        self.log("Check updated title.")
        self.assertTitleExists("Updated Title", location)

        self.log("Test RDF variants.")
        for MIME in self.RDF_VARIANTS:
            self.log("Testing {0}".format(MIME))
            headers = {
                'Accept': MIME
            }
            r = self.do_get(location, headers=headers)
            self.assertEqual(200, r.status_code, "Unable to get resource")
            self.assertIsNotNone(r.headers['Content-type'], "No content-type defined")
            self.assertEqual(MIME, r.headers['Content-type'], "Did not get expected content type")

        self.log("Delete object")
        r = self.do_delete(location)
        self.assertEqual(204, r.status_code, "Did not delete object")

        self.log("Test for tombstone")
        r = self.do_get(location)
        self.assertEqual(410, r.status_code, "Object's tombstone not found.")

    @Test
    def TestRoundtrippingBinary(self):
        """ Test roundtrip the metadata from a binary """
        self.log("Post new binary")
        r = self.do_post(headers={'Content-type': 'text/plain'}, body="Content")
        self.assertEqual(TC.CREATED, r.status_code, "Did not create binary")
        location = self.get_location(r)
        self.log("location is {}".format(location))

        body = self.do_get(location + "/" + TC.FCR_METADATA, headers={'Accept': 'application/n-triples'})
        graph = rdflib.Graph()
        graph.parse(data=body.content.decode(encoding='utf-8'), format='nt')
        for (s, p, o) in graph:
            if p in [rdflib.URIRef(TC.FEDORA_NS + "hasFixityService"),
                     rdflib.URIRef(TC.FEDORA_NS + "created"),
                     rdflib.URIRef(TC.FEDORA_NS + "createdBy"),
                     rdflib.URIRef(TC.FEDORA_NS + "lastModified"),
                     rdflib.URIRef(TC.FEDORA_NS + "lastModifiedBy"),
                     rdflib.URIRef(TC.RDF_TYPE),
                     rdflib.URIRef("http://www.loc.gov/premis/rdf/v1#hasMessageDigest")]:
                graph.remove((s, p, o))

        new_body = graph.serialize(format='nt')
        self.log("PUTTING body {}".format(new_body))

        self.log("Delete binary")
        r = self.do_delete(location)
        self.assertEqual(TC.NO_CONTENT, r.status_code, "Unable to delete binary")
        self.log("Delete binary tombstone")
        r = self.do_delete(location + "/" + TC.FCR_TOMBSTONE)
        self.assertEqual(TC.NO_CONTENT, r.status_code, "Unable to delete binary tombstone")

        time.sleep(1)
        self.log("Put binary back")
        r = self.do_put(location, headers={'Content-type': 'text/plain'}, body="Content")
        self.assertEqual(TC.CREATED, r.status_code, "Did not create binary")
        self.log("Put the description back")
        r = self.do_put(location + "/" + TC.FCR_METADATA, headers={
            'Content-type': 'application/n-triples',
            'Prefer': 'handling=lenient'
        }, body=new_body)
        self.assertEqual(TC.NO_CONTENT, r.status_code, "Did not update binary description")

        self.log("Get the body again")
        r = self.do_get(location + "/" + TC.FCR_METADATA, headers={'Accept': 'application/n-triples'})
        self.assertEqual(TC.OK, r.status_code, "Could not get the binary description")
        get_body = r.content.decode(encoding='utf-8')
        self.log("GET body {}".format(get_body))
        graph2 = rdflib.Graph()
        graph2.parse(data=get_body, format='nt')
        for triple in graph:
            if triple not in graph2:
                self.fail("Could not find triple {} in graph2".format(triple))
