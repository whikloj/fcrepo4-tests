#!/bin/env python

import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test


@register_tests
class FedoraArchivalGroupTests(FedoraTests):
    # Create test objects all inside here for easy of review
    CONTAINER = "/test_archival_groups"

    @Test
    def testCreateArchivalGroup(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)

    @Test
    def testDeleteArchivalGroupMember(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)
        self.log("Delete archivalgroup member")
        r = self.do_delete(member_location)
        self.checkResponse(TC.NO_CONTENT, r)
        self.log("Verify archivalgroup member is gone")
        r = self.do_get(member_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to delete archivalgroup member tombstone")
        r = self.do_delete(member_location + "/" + TC.FCR_TOMBSTONE)
        self.checkResponse(TC.METHOD_NOT_ALLOWED, r)

    @Test
    def putOverArchivalGroupMember(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)
        self.log("Delete archivalgroup member")
        r = self.do_delete(member_location)
        self.checkResponse(TC.NO_CONTENT, r)
        self.log("Verify archivalgroup member is gone")
        r = self.do_get(member_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup member tombstone, without header")
        r = self.do_put(member_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup member tombstone, with header")
        r = self.do_put(member_location, headers={
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CREATED, r)

    @Test
    def putOverArchivalGroupMemberWithDifferentType(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)
        self.log("Delete archivalgroup member")
        r = self.do_delete(member_location)
        self.checkResponse(TC.NO_CONTENT, r)
        self.log("Verify archivalgroup member is gone")
        r = self.do_get(member_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup member tombstone, without header")
        r = self.do_put(member_location, headers={
            "Link": self.make_type(TC.LDP_NON_RDF_SOURCE),
            "Content-type": "text/plain"
        }, body="Hello World!")
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup member tombstone, with header")
        r = self.do_put(member_location, headers={
            "Link": self.make_type(TC.LDP_NON_RDF_SOURCE),
            "Content-type": "text/plain",
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        }, body="Hello World!")
        self.checkResponse(TC.CONFLICT, r)

    @Test
    def testCreateAndDeleteArchivalGroup(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)
        self.log("Delete archivalgroup")
        r = self.do_delete(container_location)
        self.checkResponse(TC.NO_CONTENT, r)
        self.log("Verify archivalgroup is gone")
        r = self.do_get(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to delete archivalgroup tombstone")
        r = self.do_delete(container_location + "/" + TC.FCR_TOMBSTONE)
        self.checkResponse(TC.NO_CONTENT, r)

        self.log("Check for archivalgroup")
        r = self.do_get(container_location)
        self.checkResponse(TC.NOT_FOUND, r)
        self.log("Check for archivalgroup member")
        r = self.do_get(member_location)
        self.checkResponse(TC.NOT_FOUND, r)

    @Test
    def testCreateAndPutOverArchivalGroup(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)

        self.log("Try to delete archivalgroup")
        r = self.do_delete(container_location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup, without header")
        r = self.do_put(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT a new ArchivalGroupt over archivalgroup, with header")
        r = self.do_put(container_location, headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP),
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CREATED, r)

    @Test
    def testCreateAndPutOverArchivalGroupWithDifferentType(self):
        self.log("Create Archival Group container")
        r = self.do_post(self.getBaseUri(), headers={
            "Link": self.make_type(TC.ARCHIVAL_GROUP)
        })
        container_location = self.get_location(r)
        self.checkResponse(TC.CREATED, r)
        self.log("Create archivalgroup member")
        r = self.do_post(container_location)
        self.checkResponse(TC.CREATED, r)
        member_location = self.get_location(r)
        r = self.do_get(member_location)
        self.checkResponse(TC.OK, r)

        self.log("Try to delete archivalgroup")
        r = self.do_delete(container_location)
        self.checkResponse(TC.NO_CONTENT, r)
        r = self.do_get(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT over archivalgroup, without header")
        r = self.do_put(container_location)
        self.checkResponse(TC.GONE, r)

        self.log("Try to PUT a normal RDFResource over archivalgroup, with header")
        r = self.do_put(container_location, headers={
            TC.OVERWRITE_TOMBSTONE_HEADER: "true"
        })
        self.checkResponse(TC.CONFLICT, r)
