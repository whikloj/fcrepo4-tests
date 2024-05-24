#!/bin/env python

import TestConstants as TC
from abstract_fedora_tests import FedoraTests, register_tests, Test


@register_tests
class FedoraTransactionTests(FedoraTests):
    # Create test objects all inside here for easy of review
    CONTAINER = "/test_transaction"

    def createTransaction(self, admin=None):
        if admin is None:
            admin = True
        tx_location = self.get_transaction_provider()
        self.log("Create a transaction")
        r = self.do_post(tx_location, admin=admin)
        self.checkResponse(201, r)
        return self.get_location(r)

    def checkResponse(self, expected, response, tx_id=None):
        try:
            super().checkResponse(expected, response)
        except AssertionError as e:
            if tx_id is not None:
                self.do_delete(tx_id)
            raise e

    @Test
    def doCommitTest(self):
        """ Test creating and committing a transaction """
        tx_provider = self.get_transaction_provider()
        if tx_provider is None:
            self.log("Could not location transaction provider")
            self.log("Skipping test")
        else:
            transaction_id = self.createTransaction()
            self.log("Transaction is {0}".format(transaction_id))

            self.log("Get status of transaction")
            r = self.do_get(transaction_id)
            self.checkResponse(TC.NO_CONTENT, r, transaction_id)
            self.assertHeaderExists(r, "Atomic-Expires")

            self.log("Create an container in the transaction")
            transaction_headers = {
                'Atomic-Id': transaction_id
            }
            r = self.do_post(headers=transaction_headers)
            self.checkResponse(TC.CREATED, r, transaction_id)
            transaction_obj = self.get_location(r)

            self.log("Container is available inside the transaction")
            r = self.do_get(transaction_obj, headers=transaction_headers)
            self.checkResponse(TC.OK, r, transaction_id)

            self.log("Container not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.checkResponse(TC.NOT_FOUND, r, transaction_id)

            self.log("Use an invalid transaction ID")
            bad_headers = {
                'Atomic-ID': 'this-is-a-failure'
            }
            r = self.do_post(headers=bad_headers)
            self.checkResponse(TC.CONFLICT, r, transaction_id)

            self.log("Use the bare UUID of a valid transaction ID")
            diff_headers = {
                'Atomic-ID': transaction_id.replace(self.getFedoraBase() + "/" + TC.FCR_TX + "/", "")
            }
            r = self.do_post(headers=diff_headers)
            self.checkResponse(TC.CREATED, r, transaction_id)
            second_obj = self.get_location(r)

            self.log("Second container is available inside the transaction")
            r = self.do_get(second_obj, headers=transaction_headers)
            self.checkResponse(TC.OK, r, transaction_id)

            self.log("Second container not available outside the transaction")
            r = self.do_get(second_obj)
            self.checkResponse(TC.NOT_FOUND, r, transaction_id)

            self.log("Try to commit with old commit endpoint")
            r = self.do_put(transaction_id + "/commit")
            self.checkResponse(TC.NOT_FOUND, r, transaction_id)

            self.log("Commit transaction")
            r = self.do_put(transaction_id)
            self.checkResponse(TC.NO_CONTENT, r, transaction_id)

            self.log("Container is now available outside the transaction")
            r = self.do_get(transaction_obj)
            self.checkResponse(TC.OK, r)

            self.log("Transaction is no longer available")
            r = self.do_get(transaction_id)
            self.checkResponse(TC.GONE, r)

            self.log("Can't use the transaction anymore")
            r = self.do_post(headers=transaction_headers)
            self.checkResponse(TC.CONFLICT, r)

    @Test
    def doRollbackTest(self):
        """ Test creating and rolling back a transaction """
        tx_provider = self.get_transaction_provider()
        if tx_provider is None:
            self.log("Could not location transaction provider")
            self.log("Skipping test")
        else:
            transaction_id = self.createTransaction()
            self.log("Transaction is {0}".format(transaction_id))

            self.log("Create an container in the transaction")
            transaction_headers = {
                'Atomic-Id': transaction_id
            }
            r = self.do_post(headers=transaction_headers)
            self.checkResponse(TC.CREATED, r, transaction_id)
            transaction_obj = self.get_location(r)

            self.log("Container is available inside the transaction")
            r = self.do_get(transaction_obj, headers=transaction_headers)
            self.checkResponse(TC.OK, r, transaction_id)

            self.log("Container not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.checkResponse(TC.NOT_FOUND, r, transaction_id)

            self.log("Rollback transaction")
            r = self.do_delete(transaction_id)
            self.checkResponse(TC.NO_CONTENT, r, transaction_id)

            self.log("Container is still not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.checkResponse(TC.NOT_FOUND, r)

            self.log("Transaction is no longer available")
            r = self.do_get(transaction_id)
            self.checkResponse(TC.GONE, r)

            self.log("Can't use the transaction anymore")
            r = self.do_post(headers=transaction_headers)
            self.checkResponse(TC.CONFLICT, r)

    @Test
    def createAndDeleteInTwoTransaction(self):
        """ Test creating a resource in one long running transaction and deleting it in a second """
        self.log("Create a transaction")
        tx_id = self.createTransaction()

        self.log("Create a container")
        headers = {
            TC.ATOMIC_ID_HEADER: tx_id
        }
        r = self.do_post(headers=headers)
        self.checkResponse(TC.CREATED, r, tx_id)
        container_location = self.get_location(r)

        self.log("Get the container")
        r = self.do_get(container_location, headers=headers)
        self.checkResponse(TC.OK, r, tx_id)

        self.log("Commit the transaction")
        r = self.do_put(tx_id)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Get the container outside transaction")
        r = self.do_get(container_location)
        self.checkResponse(TC.OK, r)

        self.log("Create a new transaction")
        tx_id = self.createTransaction()
        headers = {
            TC.ATOMIC_ID_HEADER: tx_id
        }

        self.log("Delete the container")
        r = self.do_delete(container_location, headers=headers)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Container exists outside the transaction")
        r = self.do_get(container_location)
        self.checkResponse(TC.OK, r, tx_id)

        self.log("Container does not exist inside the transaction")
        r = self.do_get(container_location, headers=headers)
        self.checkResponse(TC.GONE, r, tx_id)

        self.log("Commit the transaction")
        r = self.do_put(tx_id)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Container does not exist outside the transaction")
        r = self.do_get(container_location)
        self.checkResponse(TC.GONE, r, tx_id)

    @Test
    def createAndDeleteInOneTransaction(self):
        """ Test creating and deleting a resource in a single transaction """
        tx_id = self.createTransaction()

        self.log("Create a container")
        headers = {
            TC.ATOMIC_ID_HEADER: tx_id
        }
        r = self.do_post(headers=headers)
        self.checkResponse(TC.CREATED, r, tx_id)
        container_location = self.get_location(r)

        self.log("Get the container: {}".format(container_location))
        r = self.do_get(container_location, headers=headers)
        self.checkResponse(TC.OK, r, tx_id)

        self.log("Delete the container")
        r = self.do_delete(container_location, headers=headers)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Check its NOT FOUND")
        r = self.do_get(container_location, headers=headers)
        self.checkResponse(TC.NOT_FOUND, r, tx_id)

        self.log("Commit the transaction")
        r = self.do_put(tx_id)
        self.checkResponse(TC.NO_CONTENT, r)

    @Test
    def testTransactionExclusion(self):
        """ Test completely removing a resource and then re-adding it in a single transaction """
        self.log("Create a container.")
        r = self.do_post()
        self.checkResponse(TC.CREATED, r)
        container_id = self.get_location(r)

        self.log("Get the container")
        r = self.do_get(container_id)
        self.checkResponse(TC.OK, r)

        tx_location = self.createTransaction()

        self.log("Delete the container in the transaction")
        txheaders = {
            TC.ATOMIC_ID_HEADER: tx_location
        }
        r = self.do_delete(container_id, headers=txheaders)
        self.checkResponse(TC.NO_CONTENT, r, tx_location)
        self.log("Ensure the container is removed in the transaction.")
        r = self.do_get(container_id, headers=txheaders)
        self.checkResponse(TC.GONE, r, tx_location)
        self.log("Inside a transaction delete the tombstone.")
        r = self.do_delete(container_id + "/" + TC.FCR_TOMBSTONE, headers=txheaders)
        self.checkResponse(TC.NO_CONTENT, r, tx_location)
        self.log("Ensure the container is totally removed in the transaction.")
        r = self.do_get(container_id, headers=txheaders)
        self.checkResponse(TC.NOT_FOUND, r, tx_location)
        self.log("Extend the transaction")
        r = self.do_post(tx_location)
        self.checkResponse(TC.NO_CONTENT, r, tx_location)
        r = self.do_post(tx_location)
        self.checkResponse(TC.NO_CONTENT, r, tx_location)

        self.log("Inside the transaction put back the container.")
        r = self.do_put(container_id, headers=txheaders)
        self.checkResponse(TC.CREATED, r, tx_location)
        self.log("Commit the transaction.")
        r = self.do_put(tx_location)
        self.checkResponse(TC.NO_CONTENT, r, tx_location)
        self.log("Verify you can still get the container.")
        r = self.do_get(container_id)
        self.checkResponse(TC.OK, r)

    @Test
    def aPlainUserTransactionRollbackInternal(self):
        """ Test a normal user performing actions in a transaction, then rolling it back using info:fedora URIs """
        child, tx_id = self.setup_user_writeable_tx()

        self.log("Rollback transaction")
        r = self.do_delete(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Test getting the child (" + child + ") in transaction")
        tx_headers = {TC.ATOMIC_ID_HEADER: tx_id}
        r = self.do_get(child, admin=False, headers=tx_headers)
        self.checkResponse(TC.CONFLICT, r, tx_id)

        self.log("Test getting the child (" + child + ") outside transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.NOT_FOUND, r, tx_id)

    @Test
    def aPlainUserTransactionRollbackExternal(self):
        """ Test a normal user performing actions in a transaction, then rolling it back using http Fedora URIs """
        child, tx_id = self.setup_user_writeable_tx(fedora_base_uri=self.getFedoraBase())

        self.log("Rollback transaction")
        r = self.do_delete(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log("Test getting the child (" + child + ") in transaction")
        tx_headers = {TC.ATOMIC_ID_HEADER: tx_id}
        r = self.do_get(child, admin=False, headers=tx_headers)
        self.checkResponse(TC.CONFLICT, r, tx_id)

        self.log("Test getting the child (" + child + ") outside transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.NOT_FOUND, r, tx_id)

    @Test
    def aPlainUserTransactionCommitInternal(self):
        """ Test a normal user performing actions in a transaction, then committing it using info:fedora URIs """
        child, tx_id = self.setup_user_writeable_tx()

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.NOT_FOUND, r, tx_id)

        self.log("Commit transaction")
        r = self.do_put(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.OK, r, tx_id)

    @Test
    def aPlainUserTransactionCommitExternal(self):
        """ Test a normal user performing actions in a transaction, then committing it using http Fedora  URIs """
        child, tx_id = self.setup_user_writeable_tx(fedora_base_uri=self.getFedoraBase())

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.NOT_FOUND, r, tx_id)

        self.log("Commit transaction")
        r = self.do_put(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.OK, r, tx_id)

    @Test
    def aSinglePlainUserTransactionCommitInternal(self):
        """ Test a normal user performing actions in a transaction, but a second user doesn't have permission
         to the transaction endpoint using info:fedora URIs """
        child, tx_id = self.single_user_tx_setup()

        self.log("Commit transaction")
        r = self.do_put(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.OK, r, tx_id)

        self.log("Try to start a transaction as the second normal user")
        tx_endpoint = self.get_transaction_provider()
        r = self.do_post(tx_endpoint, admin=self.create_user2_auth())
        self.checkResponse(TC.FORBIDDEN, r)

    @Test
    def aSinglePlainUserTransactionCommitExternal(self):
        """ Test a normal user performing actions in a transaction, but a second user doesn't have permission
                 to the transaction endpoint using http: Fedora URIs """
        child, tx_id = self.single_user_tx_setup(fedora_base_uri=self.getFedoraBase())

        self.log("Commit transaction")
        r = self.do_put(tx_id, admin=False)
        self.checkResponse(TC.NO_CONTENT, r, tx_id)

        self.log(f"Test getting the child ({child}) outside the transaction")
        r = self.do_get(child, admin=False)
        self.checkResponse(TC.OK, r, tx_id)

        self.log("Try to start a transaction as the second normal user")
        tx_endpoint = self.get_transaction_provider()
        r = self.do_post(tx_endpoint, admin=self.create_user2_auth())
        self.checkResponse(TC.FORBIDDEN, r)

    def single_user_tx_setup(self, fedora_base_uri="info:fedora"):
        """ Setup a root ACL with only one normal user allowed to access transactions. """
        root_acl = "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" \
                   "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                   "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n" \
                   "@prefix fedora: <http://fedora.info/definitions/v4/repository#> .\n" \
                   "@prefix webac: <http://fedora.info/definitions/v4/webac#> .\n" \
                   "\n" \
                   "<{1}/fcr:acl> a webac:Acl .\n" \
                   "\n" \
                   "<{1}/fcr:acl#authz> a acl:Authorization ;\n" \
                   "   rdfs:label \"Root Authorization\" ;\n" \
                   "   rdfs:comment \"By default, all non-Admin agents (foaf:Agent) only " \
                   "   have read access (acl:Read) to the repository\" ;\n" \
                   "   acl:agentClass foaf:Agent ;\n" \
                   "   acl:mode acl:Read ;\n" \
                   "   acl:accessTo <info:fedora> ;\n" \
                   "   acl:default <info:fedora> .\n" \
                   "\n" \
                   "<{1}/fcr:tx#authz_read_write> a acl:Authorization ;\n" \
                   "   rdfs:label \"Test Tx Authorization\" ;\n" \
                   "   rdfs:comment \"Provide read write access to the transaction endpoint\" ;\n" \
                   "   acl:agent \"{0}\" ;\n" \
                   "   acl:mode acl:Read, acl:Write ;\n" \
                   "   acl:accessTo <info:fedora/fcr:tx> ;\n" \
                   "   acl:default <info:fedora/fcr:tx> .\n".format(self.config[TC.USER_NAME_PARAM],
                                                                    fedora_base_uri)
        return self.setup_user_writeable_tx(root_acl=root_acl)

    def setup_user_writeable_tx(self, root_acl=None, fedora_base_uri: str = "info:fedora") -> tuple:
        """ Setup the needed containers and ACLs for the tests. """
        self.log("Update the root ACL to allow {0} to access transactions".format(self.config[TC.USER_NAME_PARAM]))

        if root_acl is None:
            root_acl = "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" \
                       "@prefix acl: <http://www.w3.org/ns/auth/acl#> .\n" \
                       "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n" \
                       "@prefix fedora: <http://fedora.info/definitions/v4/repository#> .\n" \
                       "@prefix webac: <http://fedora.info/definitions/v4/webac#> .\n" \
                       "\n" \
                       "<{0}/fcr:acl> a webac:Acl .\n" \
                       "\n" \
                       "<{0}/fcr:acl#authz> a acl:Authorization ;\n" \
                       "   rdfs:label \"Root Authorization\" ;\n" \
                       "   rdfs:comment \"By default, all non-Admin agents (foaf:Agent) only " \
                       "   have read access (acl:Read) to the repository\" ;\n" \
                       "   acl:agentClass foaf:Agent ;\n" \
                       "   acl:mode acl:Read ;\n" \
                       "   acl:accessTo <info:fedora> ;\n" \
                       "   acl:default <info:fedora> .\n" \
                       "\n" \
                       "<{0}/fcr:tx#authz_read_write> a acl:Authorization ;\n" \
                       "   rdfs:label \"Test Tx Authorization\" ;\n" \
                       "   rdfs:comment \"Provide read write access to the transaction endpoint\" ;\n" \
                       "   acl:agentClass acl:AuthenticatedAgent ;\n" \
                       "   acl:mode acl:Read, acl:Write ;\n" \
                       "   acl:accessTo <info:fedora/fcr:tx> ;\n" \
                       "   acl:default <info:fedora/fcr:tx> .\n".format(fedora_base_uri)

        r = self.do_put(self.getFedoraBase() + "/" + TC.FCR_ACL, {'Content-type': 'text/turtle'}, root_acl)
        self.checkResponse([TC.CREATED, TC.NO_CONTENT], r)

        self.log("Create a resource")
        r = self.do_post()
        self.checkResponse(TC.CREATED, r)
        container_id = self.get_location(r)

        auth = "@prefix acl: <{0}>.\n" \
               "@prefix fedora: <{1}>.\n" \
               "<#container> a acl:Authorization ;\n" \
               "  acl:mode acl:Read, acl:Write, acl:Append, acl:Control ;\n" \
               "  acl:accessTo <{2}> ;\n" \
               "  acl:default <{2}> ;\n" \
               "  acl:agent \"{3}\" .\n".format(TC.ACL_NS, TC.FEDORA_NS, container_id,
                                                self.config[TC.USER_NAME_PARAM])

        self.log("Set up ACL with user having full access.")
        r = self.do_put(container_id + "/" + TC.FCR_ACL, headers={"Content-type": "text/turtle"}, body=auth,
                        admin=True)
        self.checkResponse(TC.CREATED, r)

        self.log("Have user read the item")
        r = self.do_get(container_id, admin=False)
        self.checkResponse(TC.OK, r)
        self.log("Have the user patch the item")
        patch = "INSERT DATA { <> <http://purl.org/dc/elements/1.1/title> \"Some title\" }"
        r = self.do_patch(container_id, headers={"Content-type": "application/sparql-update"}, body=patch,
                          admin=False)
        self.checkResponse(TC.NO_CONTENT, r)
        self.log("Start a transaction")
        tx_id = self.createTransaction(False)
        tx_headers = {TC.ATOMIC_ID_HEADER: tx_id}
        self.log("Add a child object")
        r = self.do_post(container_id, headers=tx_headers, admin=False)
        self.checkResponse(TC.CREATED, r, tx_id)
        child = self.get_location(r)
        self.log(f"Test getting the child ({child}) in transaction")
        r = self.do_get(child, admin=False, headers=tx_headers)
        self.checkResponse(TC.OK, r, tx_id)
        self.log(f"Test getting the child ({child}) outside the transaction")
        return child, tx_id
