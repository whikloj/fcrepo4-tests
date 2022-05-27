#!/bin/env python

import TestConstants
from abstract_fedora_tests import FedoraTests, register_tests, Test
import json
import pyjq
import uuid


@register_tests
class FedoraIndirectTests(FedoraTests):

    # Create test objects all inside here for ease of review/removal
    CONTAINER = "/test_indirect"

    @Test
    def doPcdmIndirect(self):
        self.log("Create a PCDM container")
        basic_headers = {
            'Link': self.make_type(TestConstants.LDP_BASIC),
            'Content-type': 'text/turtle'
        }
        r = self.do_post(self.getBaseUri(), headers=basic_headers, body=TestConstants.OBJECT_TTL)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        pcdm_container_location = self.get_location(r)

        self.log("Create a PCDM Collection")
        r = self.do_post(self.getBaseUri(), headers=basic_headers, body=TestConstants.OBJECT_TTL)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        pcdm_collection_location = self.get_location(r)

        self.log("Create indirect container inside PCDM collection")
        indirect_headers = {
            'Link': self.make_type(TestConstants.LDP_INDIRECT),
            'Content-type': 'text/turtle'
        }
        pcdm_indirect = "@prefix dc: <http://purl.org/dc/elements/1.1/> ." \
                        "@prefix pcdm: <http://pcdm.org/models#> ." \
                        "@prefix ore: <http://www.openarchives.org/ore/terms/> ." \
                        "@prefix ldp: <http://www.w3.org/ns/ldp#> ." \
                        "<> dc:title \"Members Container\" ;" \
                        " ldp:membershipResource <{0}> ;" \
                        " ldp:hasMemberRelation pcdm:hasMember ;" \
                        " ldp:insertedContentRelation ore:proxyFor .".format(pcdm_collection_location)
        r = self.do_post(pcdm_collection_location, headers=indirect_headers, body=pcdm_indirect)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        members_location = self.get_location(r)

        self.log("Create a proxy object")
        pcdm_proxy = "@prefix pcdm: <http://pcdm.org/models#>" \
                     "@prefix ore: <http://www.openarchives.org/ore/terms/>" \
                     "<> a pcdm:Object ;" \
                     "ore:proxyFor <{0}> .".format(pcdm_container_location)
        r = self.do_post(members_location, headers=basic_headers, body=pcdm_proxy)
        self.assertEqual(201, r.status_code, "Did not get expected status code")

        self.log("Check PCDM Collection for a new pcmd:hasMember property to PCDM container")
        headers = {
            'Accept': TestConstants.JSONLD_MIMETYPE
        }
        r = self.do_get(pcdm_collection_location, headers=headers)
        self.assertEqual(200, r.status_code, "Did not get expected status code")

        body = r.content.decode('UTF-8')
        body_json = json.loads(body)
        hasmembers = pyjq.all('.[] | ."http://pcdm.org/models#hasMember" | .[]."@id"', body_json)
        found_member = False
        for member in hasmembers:
            if member == pcdm_container_location:
                found_member = True
        self.assertTrue(found_member, "Did not find hasMember property")

    @Test
    def doAddIndirect(self):
        read_only = str(uuid.uuid4())
        headers = {
            'Slug': read_only
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        read_only_location = self.get_location(r)
        self.log("making a read-only resource : {0}".format(read_only_location))
        self.assertEqual(201, r.status_code, "Did not get expected status code")

        turtle_headers = {
            'Content-type': TestConstants.TURTLE_MIMETYPE
        }
        read_only_acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> . \n"\
            "<#readauthz> a acl:Authorization ; \n"\
            "acl:agent \"{0}\" ;\n" \
            "acl:mode acl:Read ;\n" \
            "acl:accessTo <{1}> .".format(self.config[TestConstants.USER_NAME_PARAM], read_only_location)
        self.log("adding an acl to the read-only resource")
        r = self.do_put(read_only_location + "/" + TestConstants.FCR_ACL, headers=turtle_headers, body=read_only_acl)
        self.assertEqual(201, r.status_code, "Did not get expected status code")

        self.log("Do get as testuser")
        r = self.do_get(read_only_location, admin=False)
        self.assertEqual(200, r.status_code, "Did not get expected status code")

        patch_headers = {
            "Content-type": TestConstants.SPARQL_UPDATE_MIMETYPE
        }
        patch_body = "INSERT DATA { <> <http://purl.org/dc/elements/1.1/title> \"Changed it\"}"
        self.log("Try patch as testuser")
        r = self.do_patch(read_only_location, headers=patch_headers, body=patch_body, admin=False)
        self.assertEqual(403, r.status_code, "Did not get expected status code")

        writeable = str(uuid.uuid4())
        headers = {
            'Slug': writeable
        }
        r = self.do_post(self.getBaseUri(), headers=headers)
        self.assertEqual(201, r.status_code, "Did not get expected status code")
        writeable_location = self.get_location(r)
        self.log("create a new writeable resource at {0}".format(writeable_location))

        writeable_acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                "<#writeauth> a acl:Authorization ;\n" \
                "   acl:agent \"{0}\" ;\n" \
                "   acl:mode acl:Read, acl:Write ;\n" \
                "   acl:accessTo <{1}> ;\n" \
                "   acl:default <{1}> .".format(self.config[TestConstants.USER_NAME_PARAM], writeable_location)
        self.log("create an ACl on the writeable resource")
        r = self.do_put(writeable_location + "/" + TestConstants.FCR_ACL, headers=turtle_headers, body=writeable_acl)
        self.assertEqual(201, r.status_code, "Did not get expected status code")

        self.log("Test writing inside the writeable resource as testuser")
        r = self.do_post(writeable_location, admin=False)
        self.assertEqual(201, r.status_code, "Did not get expected status code")

        indirect_template = "@prefix ldp: <http://www.w3.org/ns/ldp#> .\n" \
                "@prefix example: <http://www.example.org/example1#> .\n" \
                "@prefix dc: <http://purl.org/dc/elements/1.1/> .\n" \
                "<> ldp:insertedContentRelation <http://example.org/test#something> ;\n" \
                "ldp:membershipResource <{0}> ;\n" \
                "ldp:hasMemberRelation <http://example.org/test#predicateToCreate> ;\n" \
                "dc:title \"The indirect container\" ."
        indirect_body = indirect_template.format(read_only_location)
        headers = {
            "Slug": "indirect",
            "Content-type": TestConstants.TURTLE_MIMETYPE,
            'Link': self.make_type(TestConstants.LDP_INDIRECT)
        }
        self.log("Try to create an indirect referencing a read-only resource")
        r = self.do_post(writeable_location, headers=headers, body=indirect_body, admin=False)
        self.assertEqual(403, r.status_code, "Did not get expected status code")

        headers = {
            'Slug': 'mockTarget',
        }
        self.log("Try to create a new mock target")
        r = self.do_post(writeable_location, headers=headers, admin=False)
        self.assertEqual(201, r.status_code, 'Did not get expected status code')
        mockTarget_location = self.get_location(r)

        headers = {
            "Slug": "indirect",
            "Content-type": TestConstants.TURTLE_MIMETYPE,
            'Link': self.make_type(TestConstants.LDP_INDIRECT)
        }
        mock_body = indirect_template.format(mockTarget_location)
        self.log("Create an indirect container referencing an allowed target")
        r = self.do_post(writeable_location, headers=headers, body=mock_body, admin=False)
        self.assertEqual(201, r.status_code, 'Did not get expected status code')
        indirect_location = self.get_location(r)

        insert_delete_patch = "prefix ldp: <http://www.w3.org/ns/ldp#> \n" \
                "DELETE {{ <> ldp:membershipResource ?o }} \n" \
                "INSERT {{ <> ldp:membershipResource <{0}> }} \n" \
                "WHERE {{ <> ldp:membershipResource ?o }}".format(read_only_location)
        self.log("Try to patch the indirect from allowed to not-allowed")
        r = self.do_patch(indirect_location, headers=patch_headers, body=insert_delete_patch, admin=False)
        self.assertEqual(403, r.status_code, 'Did not get expected status code')

        delete_data_body = "prefix ldp: <http://www.w3.org/ns/ldp#> \n" \
                "DELETE DATA {{ <> ldp:membershipResource <{0}> }}".format(mockTarget_location)
        self.log("Try to DELETE DATA the membershipResource")
        r = self.do_patch(indirect_location, headers=patch_headers, body=delete_data_body, admin=False)
        self.assertEqual(204, r.status_code, 'Did not get expected status code')

        insert_data_body = "prefix ldp: <http://www.w3.org/ns/ldp#> \n" \
                "INSERT DATA {{ <> ldp:membershipResource <{0}> }}".format(read_only_location)
        self.log("Try to INSERT DATA the membershipResource")
        r = self.do_patch(indirect_location, headers=patch_headers, body=insert_data_body, admin=False)
        self.assertEqual(403, r.status_code, 'Did not get expected status code')

        self.log("Try to patch the indirect from allowed to not-allowed as Admin")
        r = self.do_patch(indirect_location, headers=patch_headers, body=insert_delete_patch)
        self.assertEqual(204, r.status_code, 'Did not get expected status code')

        self.log("Now try to post to the indirect")
        post_body = "@prefix ldp: <http://www.w3.org/ns/ldp#> .\n" \
                "@prefix test: <http://example.org/test#> .\n\n" \
                "<> test:something <{0}> .".format(mockTarget_location)
        r = self.do_post(indirect_location, headers=turtle_headers, body=post_body, admin=False)
        self.assertEqual(403, r.status_code, "Did not get expected status code")

        self.log("Indirect is {0}\nread-only is {1}".format(indirect_location, read_only_location))
