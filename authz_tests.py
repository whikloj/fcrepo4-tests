#!/bin/env python

import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test
import random
import uuid


@register_tests
class FedoraAuthzTests(FedoraTests):
    # Create test objects all inside here for easy of review
    CONTAINER = "/test_authz"

    COVER_ACL = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                "@prefix pcdm: <http://pcdm.org/models#> .\n" \
                "<#writeauth> a acl:Authorization ;" \
                "acl:accessToClass pcdm:Object ;" \
                "acl:mode acl:Read, acl:Write;" \
                "acl:default <{0}>; " \
                "acl:agent \"{1}\" ."

    FILES_ACL = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                "@prefix pcdm: <http://pcdm.org/models#> .\n" \
                "<#writeauth> a acl:Authorization ;" \
                "acl:accessTo <{0}> ;" \
                "acl:mode acl:Read, acl:Write;" \
                "acl:agent \"{1}\" ."

    def verifyAuthEnabled(self):
        self.log("Checking that authZ is enabled")
        lst = [random.choice('0123456789abcdef') for n in range(16)]
        random_string = "".join(lst)

        temp_auth = FedoraTests.create_auth(random_string, random_string)
        r = self.do_get(self.getFedoraBase(), admin=temp_auth)
        if 401 != r.status_code:
            self.log("It appears that authentication is not enabled on your repository.")
            quit()

    @staticmethod
    def getAclUri(response):
        acls = FedoraAuthzTests.get_link_headers(response)
        try:
            return acls['acl'][0]
        except KeyError:
            Exception("No acl link header found")

    @Test
    def doAuthTests(self):
        self.verifyAuthEnabled()

        self.log("Create \"cover\" container")
        r = self.do_put(self.getBaseUri() + "/cover")
        self.checkResponse(201, r)
        cover_location = self.get_location(r)
        cover_acl = FedoraAuthzTests.getAclUri(r)

        self.log("Make \"cover\" a pcdm:Object")
        sparql = "PREFIX pcdm: <http://pcdm.org/models#>" \
                 "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>" \
                 "INSERT { <> rdf:type pcdm:Object } WHERE { }"
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(cover_location, headers=headers, body=sparql)
        self.checkResponse(204, r)

        self.log("Verify no current ACL")
        r = self.do_get(cover_acl)
        self.checkResponse(404, r)

        self.log("Add ACL to \"cover\"")
        headers = {
            'Content-type': 'text/turtle'
        }
        body = self.COVER_ACL.format(cover_location, self.config[TC.USER_NAME_PARAM])
        r = self.do_put(cover_acl, headers=headers, body=body)
        self.checkResponse(201, r)

        self.log("Create \"files\" inside \"cover\"")
        r = self.do_put(cover_location + "/files")
        self.checkResponse(201, r)
        files_location = self.get_location(r)
        files_acl = FedoraAuthzTests.getAclUri(r)

        self.log("Anonymous can't access \"cover\"")
        r = self.do_get(cover_location, admin=None)
        self.checkResponse(401, r)

        self.log("Anonymous can't access \"cover/files\"")
        r = self.do_get(files_location, admin=None)
        self.checkResponse(401, r)

        self.log("{0} can access \"cover\"".format(self.config[TC.ADMIN_USER_PARAM]))
        r = self.do_get(cover_location)
        self.checkResponse(200, r)

        self.log("{0} can access \"cover/files\"".format(self.config[TC.ADMIN_USER_PARAM]))
        r = self.do_get(files_location)
        self.checkResponse(200, r)

        self.log("{0} can access \"cover\"".format(self.config[TC.USER_NAME_PARAM]))
        r = self.do_get(cover_location, admin=False)
        self.checkResponse(200, r)

        self.log("{0} can access \"cover/files\"".format(self.config[TC.USER_NAME_PARAM]))
        r = self.do_get(files_location, admin=False)
        self.checkResponse(200, r)

        auth = self.create_auth(self.config[TC.USER2_NAME_PARAM],
                                self.config[TC.USER2_PASS_PARAM])
        self.log("{0} can't access \"cover\"".format(self.config[TC.USER2_NAME_PARAM]))
        r = self.do_get(cover_location, admin=auth)
        self.checkResponse(403, r)

        self.log("{0} can't access \"cover/files\"".format(self.config[TC.USER2_NAME_PARAM]))
        r = self.do_get(files_location, admin=auth)
        self.checkResponse(403, r)

        self.log("Verify \"cover/files\" has no ACL")
        r = self.do_get(files_acl)
        self.checkResponse(404, r)

        self.log("PUT Acl to \"cover/files\" to allow access for {0}".format(self.config[TC.USER2_NAME_PARAM]))
        headers = {
            'Content-type': 'text/turtle'
        }
        body = self.FILES_ACL.format(files_location, self.config[TC.USER2_NAME_PARAM])
        r = self.do_put(files_acl, headers=headers, body=body)
        self.checkResponse(201, r)

        self.log("{0} can't access \"cover\"".format(self.config[TC.USER2_NAME_PARAM]))
        r = self.do_get(cover_location, admin=auth)
        self.checkResponse(403, r)

        self.log("{0} can access \"cover/files\"".format(self.config[TC.USER2_NAME_PARAM]))
        r = self.do_get(files_location, admin=auth)
        self.checkResponse(200, r)

    @Test
    def doDirectIndirectAuthTests(self):
        self.verifyAuthEnabled()

        self.log("Create a target container")
        r = self.do_post()
        self.checkResponse(201, r)
        target_location = self.get_location(r)
        target_acl = FedoraAuthzTests.getAclUri(r)

        self.log("Create a write container")
        r = self.do_post()
        self.checkResponse(201, r)
        write_location = self.get_location(r)
        write_acl = FedoraAuthzTests.getAclUri(r)

        self.log("Make sure the /target resource is readonly")
        target_ttl = "@prefix acl: <{2}> .\n" \
                     "<#readauthz> a acl:Authorization ;\n" \
                     "  acl:agent \"{0}\" ;\n" \
                     "  acl:mode acl:Read ;\n" \
                     "  acl:accessTo <{1}> .\n".format(self.config[TC.USER_NAME_PARAM], target_location,
                                                       TC.ACL_NS)
        headers = {
            'Content-type': 'text/turtle'
        }
        r = self.do_put(target_acl, headers=headers, body=target_ttl)
        self.checkResponse(201, r)

        self.log("Make sure the write resource is writable by \"{0}\"".format(self.config[TC.USER_NAME_PARAM]))
        write_ttl = "@prefix acl: <{2}> .\n" \
                    "<#writeauth> a acl:Authorization ;\n" \
                    "   acl:agent \"{0}\" ;\n" \
                    "   acl:mode acl:Read, acl:Write ;\n" \
                    "   acl:accessTo <{1}> ;\n" \
                    "   acl:default <{1}> .\n".format(self.config[TC.USER_NAME_PARAM], write_location,
                                                      TC.ACL_NS)
        r = self.do_put(write_acl, headers=headers, body=write_ttl)
        self.checkResponse(201, r)

        self.log("Verify that \"{0}\" can create a simple resource under write resource (POST)".format(
            self.config[TC.USER_NAME_PARAM]))
        r = self.do_post(write_location, admin=False)
        self.checkResponse(201, r)

        uuid_value = str(uuid.uuid4())
        self.log("Verify that \"{0}\" can create a simple resource under write resource (PUT)".format(
            self.config[TC.USER_NAME_PARAM]))
        r = self.do_put(write_location + "/" + uuid_value, admin=False)
        self.checkResponse(201, r)

        self.log("Verify that \"{0}\" CANNOT create a resource under target resource".format(
            self.config[TC.USER_NAME_PARAM]))
        r = self.do_post(target_location, admin=False)
        self.checkResponse(403, r)

        self.log(
            "Verify that \"{0}\" CANNOT create direct or indirect containers that reference target resources".format(
                self.config[TC.USER_NAME_PARAM]))
        headers = {
            'Content-type': 'text/turtle',
            'Link': self.make_type(TC.LDP_DIRECT)
        }
        direct_ttl = "@prefix ldp: <{0}> .\n" \
                     "@prefix test: <http://example.org/test#> .\n" \
                     "<>  ldp:membershipResource <{1}> ;\n" \
                     "ldp:hasMemberRelation test:predicateToCreate .\n".format(TC.LDP_NS, target_location)
        r = self.do_post(write_location, headers=headers, body=direct_ttl, admin=False)
        self.checkResponse(403, r)

        headers = {
            'Content-type': 'text/turtle',
            'Link': self.make_type(TC.LDP_INDIRECT)
        }
        indirect_ttl = "@prefix ldp: <{0}> .\n" \
                       "@prefix test: <http://example.org/test#> .\n" \
                       "<> ldp:insertedContentRelation test:something ;\n" \
                       "ldp:membershipResource <{1}> ;\n" \
                       "ldp:hasMemberRelation test:predicateToCreate .\n".format(TC.LDP_NS, target_location)
        r = self.do_post(write_location, headers=headers, body=indirect_ttl, admin=False)
        self.checkResponse(403, r)

        self.log("Go ahead and create the indirect and direct containers as admin")
        r = self.do_post(write_location, headers=headers, body=direct_ttl)
        self.checkResponse(201, r)
        direct_location = self.get_location(r)
        r = self.do_post(write_location, headers=headers, body=indirect_ttl)
        self.checkResponse(201, r)
        indirect_location = self.get_location(r)

        self.log("Attempt to verify that \"{0}\" can not actually create relationships on the readonly resource via " \
                 "direct or indirect container".format(self.config[TC.USER_NAME_PARAM]))
        r = self.do_post(direct_location, admin=False)
        self.assertEqual(403, r.status_code, "Did not get expected status code")
        r = self.do_post(indirect_location, admin=False)
        self.assertEqual(403, r.status_code, "Did not get expected status code")

        self.log("Verify that \"{0}\" can still create a simple resource under write resource (POST)".format(
            self.config[TC.USER_NAME_PARAM]))
        r = self.do_post(write_location, admin=False)
        self.checkResponse(201, r)

        uuid_value = str(uuid.uuid4())
        self.log("Verify that \"{0}\" can still create a simple resource under write resource (PUT)".format(
            self.config[TC.USER_NAME_PARAM]))
        r = self.do_put(write_location + "/" + uuid_value, admin=False)
        self.checkResponse(201, r)

    @Test
    def multipleAuthzCreatePermissiveSet(self):
        self.verifyAuthEnabled()

        self.log("Create a target container")
        r = self.do_post()
        self.checkResponse(201, r)
        target_location = self.get_location(r)
        target_acl = FedoraAuthzTests.getAclUri(r)

        double_ttl = "@prefix acl: <{2}> .\n" \
                     "<#readonly> a acl:Authorization ;\n" \
                     "   acl:agent \"{0}\" ;\n" \
                     "   acl:mode acl:Read ;\n" \
                     "   acl:accessTo <{1}> .\n" \
                     "<#readwrite> a acl:Authorization ;\n" \
                     "   acl:agent \"{0}\" ;\n" \
                     "   acl:mode acl:Write ;\n" \
                     "   acl:accessTo <{1}> .\n".format(self.config[TC.USER_NAME_PARAM], target_location,
                                                        TC.ACL_NS)
        headers = {
            'Content-type': TC.TURTLE_MIMETYPE
        }

        self.log("Add ACL with one read and one write authz for the same URI.")
        r = self.do_put(target_acl, headers=headers, body=double_ttl)
        self.checkResponse(201, r)

        self.log("Check we can read")
        r = self.do_get(target_location, admin=False)
        self.checkResponse(200, r)

        self.log("Check we can write")
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        body = "prefix dc: <{0}> INSERT {{ <> dc:title \"A new title\" }} WHERE {{}}".format(TC.PURL_NS)
        r = self.do_patch(target_location, headers=headers, body=body)
        self.checkResponse(204, r)

    @Test
    def testAllThingsPointTogether(self):
        self.verifyAuthEnabled()

        self.log("Create a target binary")
        headers = {
            'Content-type': 'text/plain',
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE)
        }
        r = self.do_post(headers=headers, body="this is a test payload")
        self.checkResponse(201, r)
        binary_location = self.get_location(r)
        expected_acl = binary_location + "/fcr:acl"
        acl_location = FedoraAuthzTests.getAclUri(r)
        binary_description = self.find_binary_description(r)

        self.assertNotEqual(binary_location, binary_description)

        self.log("Check binary's acl link header is correct.")
        self.checkValue(expected_acl, acl_location)

        self.log("Check binary description's acl link header is correct")

        r = self.do_get(binary_location)
        self.checkResponse(200, r)
        acl_location = FedoraAuthzTests.getAclUri(r)
        self.checkValue(expected_acl, acl_location)

        self.log("Check binary timemap's acl link header is correct.")
        binary_versions = binary_location + "/fcr:versions"
        r = self.do_get(binary_versions)
        self.checkResponse(200, r)
        acl_location = FedoraAuthzTests.getAclUri(r)
        self.checkValue(expected_acl, acl_location)

        self.log("Create a version of binary")
        r = self.do_post(parent=binary_versions)
        self.checkResponse(201, r)
        memento_location = self.get_location(r)

        self.log("Check binary description timemap's acl link header is correct.")
        binary_metadata_versions = binary_description + "/fcr:versions"
        r = self.do_get(binary_metadata_versions)
        self.checkResponse(200, r)
        acl_location = FedoraAuthzTests.getAclUri(r)
        self.checkValue(expected_acl, acl_location)

    @Test
    def doBinaryAndMetadataShareACL(self):
        self.verifyAuthEnabled()

        self.log("Create a target binary")
        headers = {
            'Content-type': 'text/plain',
            'Link': self.make_type(TC.LDP_NON_RDF_SOURCE)
        }
        r = self.do_post(headers=headers, body="this is a test payload")
        self.checkResponse(201, r)
        binary_location = self.get_location(r)
        acl_location = FedoraAuthzTests.getAclUri(r)
        binary_description = self.find_binary_description(r)

        self.log("Add ACL allowing write to metadata but not binary for user")
        binary_acl = "@prefix acl: <{0}> .\n" \
                     "<#binary> a acl:Authorization ;\n" \
                     "  acl:mode acl:Write ;\n" \
                     "  acl:accessTo <{1}> ;\n" \
                     "  acl:agent \"{2}\" .\n".format(TC.ACL_NS, binary_location,
                                                      self.config[TC.USER_NAME_PARAM])
        headers = {
            'Content-type': TC.TURTLE_MIMETYPE
        }
        r = self.do_put(acl_location, headers=headers, body=binary_acl)
        self.checkResponse(201, r)

        self.log("Try to read binary")
        r = self.do_head(binary_location, admin=False)
        self.checkResponse(403, r)

        self.log("Try to write binary")
        headers = {
            'Content-type': 'text/plain'
        }
        r = self.do_put(binary_location, headers=headers, body="This is a new body", admin=False)
        self.checkResponse(204, r)

        self.log("Try to read the metadata")
        r = self.do_get(binary_description, admin=False)
        self.checkResponse(403, r)

        self.log("Try to patch metadata")
        patch_body = "prefix dc: <{0}> INSERT DATA {{ <> dc:title \"Updated title\"}}".format(TC.PURL_NS)
        headers = {
            'Content-type': TC.SPARQL_UPDATE_MIMETYPE
        }
        r = self.do_patch(binary_description, patch_body, headers=headers, admin=False)
        self.checkResponse(204, r)

    @Test
    def testContainerWithAccessToClass(self):

        self.verifyAuthEnabled()

        self.log("Create a container")
        r = self.do_post()
        location = self.get_location(r)
        acl_location = self.getAclUri(r)
        versions_location = location + "/" + TC.FCR_VERSIONS

        full_acl = "@prefix acl: <{0}> .\n" \
                   "@prefix fedora: <{1}> .\n" \
                   "@prefix memento: <{2}> .\n" \
                   "<#container> a acl:Authorization ;\n" \
                   "  acl:mode acl:Read ;\n" \
                   "  acl:accessTo <{3}> ;\n" \
                   "  acl:agent \"{4}\" .\n" \
                   "<#timemap> a acl:Authorization ;\n" \
                   "  acl:mode acl:Read ;\n" \
                   "  acl:accessToClass fedora:TimeMap ;\n" \
                   "  acl:default <{3}> ;\n" \
                   "  acl:agent \"{4}\" .\n" \
                   "<#memento> a acl:Authorization ;\n" \
                   "  acl:mode acl:Read ;\n" \
                   "  acl:accessToClass memento:Memento ;\n" \
                   "  acl:default <{3}> ;\n" \
                   "  acl:agent \"{5}\" .\n".format(TC.ACL_NS, TC.FEDORA_NS, TC.MEMENTO_NS,
                                                    location, self.config[TC.USER_NAME_PARAM],
                                                    self.config[TC.ADMIN_USER_PARAM])
        turtle_headers = {
            'Content-type': TC.TURTLE_MIMETYPE
        }

        user2 = self.create_user2_auth()

        self.log("Put ACL giving test user 1 read access to container and timemap but not mementos")
        r = self.do_put(acl_location, headers=turtle_headers, body=full_acl)
        self.checkResponse(201, r)

        self.log("Create a Memento as admin")
        r = self.do_post(versions_location)
        self.checkResponse(201, r)
        memento_location = self.get_location(r)

        self.log("Try to get container as test user 1")
        r = self.do_get(location, admin=False)
        self.checkResponse(200, r)

        self.log("Try to get container as test user 2")
        r = self.do_get(location, admin=user2)
        self.checkResponse(403, r)

        self.log("Try to get timemap as test user 1")
        r = self.do_get(versions_location, admin=False)
        self.checkResponse(200, r)

        self.log("Try to get timemap as test user 2")
        r = self.do_get(versions_location, admin=user2)
        self.checkResponse(403, r)

        self.log("Check that memento exists as admin")
        r = self.do_get(memento_location)
        self.checkResponse(200, r)

        self.log("Try to get memento as test user 1")
        r = self.do_get(memento_location, admin=False)
        self.checkResponse(200, r)

        self.log("Try to get memento as test user 2")
        r = self.do_get(memento_location, admin=user2)
        self.checkResponse(403, r)

    @Test
    def testPermissionsDoNotExtendInTx(self):
        self.verifyAuthEnabled()
        self.log("Create a container")
        r = self.do_post()
        location = self.get_location(r)
        acl_location = self.getAclUri(r)
        headers = {
            'Content-type': TC.TURTLE_MIMETYPE
        }
        readwriteString = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                          "<#readauthz> a acl:Authorization ;\n" \
                          "   acl:agent \"{0}\" ;\n" \
                          "   acl:mode acl:Read, acl:Write ;\n" \
                          "   acl:accessTo <{1}> .".format(self.config[TC.USER_NAME_PARAM], location)

        r = self.do_put(acl_location, headers=headers, body=readwriteString)
        self.checkResponse(201, r)
        # Test that user28 can read target resource.
        r = self.do_get(location, admin=False)
        self.checkResponse(200, r)
        # Test that user28 can patch target resource.
        patchString = "prefix dc: <http://purl.org/dc/elements/1.1/> INSERT { <> dc:title " \
                      "\"new title\" } WHERE {}"
        patch_headers = {
            'Content-type': 'application/sparql-update'
        }
        r = self.do_patch(location, headers=patch_headers, body=patchString, admin=False)
        self.checkResponse(204, r)
        # Test that user28 can post to target resource.
        r = self.do_post(location, admin=False)
        self.checkResponse(201, r)
        childResource = self.get_location(r)
        # Test that user28 cannot patch the child resource(ACL is not acl: default).
        r = self.do_patch(childResource, headers=patch_headers, body=patchString, admin=False)
        self.checkResponse(403, r)
        # Test that user28 cannot post to a child resource.
        r = self.do_post(childResource, admin=False)
        self.checkResponse(403, r)
        # Test another user cannot access the target resource.
        r = self.do_get(location, admin=self.create_user2_auth())
        self.checkResponse(403, r)
        # Get the transaction endpoint.
        transactionEndpoint = self.get_transaction_provider()
        # Create a transaction.
        r = self.do_post(transactionEndpoint)
        self.checkResponse(201, r)
        transactionId = self.get_location(r)
        self.log("transaction ID {0}".format(transactionId))
        # Test user28 can post to target resource in a transaction.
        txHeaders = {
            'Atomic-ID': transactionId
        }
        r = self.do_post(location, headers=txHeaders, admin=False)
        self.checkResponse(201, r)
        txChild = self.get_location(r)
        # Test user28 cannot post to the child in a transaction.
        r = self.do_post(txChild, headers=txHeaders, admin=False)
        self.checkResponse(403, r)

    @Test
    def testGroupAuth(self):
        self.log("THIS TEST REQUIRES FEDORA TO HAVE THE TESTSUITE WEBID PREFIX")
        agentGroup = "@prefix    acl:  <http://www.w3.org/ns/auth/acl#>. " \
                     "@prefix  vcard:  <http://www.w3.org/2006/vcard/ns#>. " \
                     "<> a vcard:Group;" \
                     "vcard:hasMember  <{}{}>.".format(TC.USER_URL_PREFIX,
                                                       self.config[TC.USER_NAME_PARAM])
        head = {
            'Content-type': TC.TURTLE_MIMETYPE
        }
        r = self.do_post(headers=head, body=agentGroup)
        self.checkResponse(201, r)
        group_location = self.get_location(r)

        r = self.do_post()
        self.checkResponse(201, r)
        target_location = self.get_location(r)

        acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> ." \
              "@prefix foaf: <http://xmlns.com/foaf/0.1/> ." \
              "<#authorization> a acl:Authorization; " \
              "acl:accessTo    <{}>;" \
              "acl:mode acl:Read, acl:Write;" \
              "acl:agentGroup  <{}>.".format(target_location, group_location)

        r = self.do_put(target_location + "/" + TC.FCR_ACL, headers=head, body=acl)
        self.checkResponse(201, r)

        r = self.do_get(target_location, admin=False)
        self.checkResponse(200, r)

    @Test
    def testControlOnlyPut(self):
        r = self.do_post()
        self.checkResponse(201, r)
        resource_uri = self.get_location(r)

        control_acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                      "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n" \
                      "<#restricted> a acl:Authorization ;\n" \
                      "acl:agent \"{0}\" ;\n" \
                      "acl:mode acl:Control;\n" \
                      "acl:default <{1}> ;\n" \
                      "acl:accessTo <{1}> .".format(self.config[TC.USER_NAME_PARAM], resource_uri)
        head = {
            'Content-type': TC.TURTLE_MIMETYPE
        }
        r = self.do_put(resource_uri + "/" + TC.FCR_ACL, headers=head, body=control_acl)
        self.checkResponse(201, r)

        # Verify that testuser can not read the resource
        r = self.do_get(resource_uri, admin=False)
        self.checkResponse(403, r)

        new_control_acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                          "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n" \
                          " <#openaccess> a acl:Authorization ;" \
                          " acl:mode acl:Read ;\n" \
                          " acl:agentClass foaf:Agent ; \n" \
                          " acl:accessTo <{}> .".format(resource_uri)
        # Update ACL as testuser
        r = self.do_put(resource_uri + "/" + TC.FCR_ACL, headers=head, body=new_control_acl, admin=False)
        self.checkResponse(204, r)

        # Check that now testuser can read
        r = self.do_get(resource_uri, admin=False)
        self.checkResponse(200, r)

    @Test
    def testCanAccessToAndAccessToClass(self):
        r = self.do_post()
        self.checkResponse(201, r)
        resource_uri = self.get_location(r)

        acl = "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
              "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n" \
              "@prefix pcdm: <http://pcdm.org/models#> .\n" \
              " <#openaccess> a acl:Authorization ;" \
              " acl:mode acl:Read ;\n" \
              " acl:agentClass foaf:Agent ; \n" \
              " acl:accessTo <{}> ; \n" \
              " acl:accessToClass pcdm:Object .".format(resource_uri)

        headers = {
            'Content-type': TC.TURTLE_MIMETYPE
        }

        r = self.do_put(resource_uri + "/" + TC.FCR_ACL, headers=headers, body=acl)
        self.checkResponse(400, r)
        self.assertContrainedByHeaderExists(r)

    @Test
    def testPutInvalidAcl(self):
        self.log("Create a mock container to use as the ACL")
        r = self.do_post()
        self.checkResponse(201, r)
        resource_uri = self.get_location(r)

        headers = {
            'Link': "<{}>; rel=\"acl\"".format(resource_uri)
        }
        # Make a new resource trying to define the location of the ACL.
        r = self.do_post(headers=headers)
        self.checkResponse(400, r)
        self.assertContrainedByHeaderExists(r)
