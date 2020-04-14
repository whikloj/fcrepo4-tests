#!/bin/env python

import TestConstants
from abstract_fedora_tests import FedoraTests, register_tests, Test


@register_tests
class FedoraTransactionTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_transaction"

    def get_transaction_provider(self):
        headers = {
            'Accept': TestConstants.JSONLD_MIMETYPE
        }
        r = self.do_head(self.getFedoraBase(), headers=headers)
        self.assertEqual(200, r.status_code, "Did not get expected response")
        link_headers = self.get_link_headers(r)
        if TestConstants.FEDORA_TX_ENDPOINT_REL in link_headers.keys():
            return link_headers.get(TestConstants.FEDORA_TX_ENDPOINT_REL)[0]
        return None

    @Test
    def doCommitTest(self):
        tx_provider = self.get_transaction_provider()
        if tx_provider is None:
            self.log("Could not location transaction provider")
            self.log("Skipping test")
        else:
            self.log("Create a transaction")
            r = self.do_post(tx_provider)
            self.assertEqual(201, r.status_code, "Did not get expected response code")
            transaction_id = self.get_location(r)
            self.log("Transaction is {0}".format(transaction_id))

            self.log("Get status of transaction")
            r = self.do_get(transaction_id)
            self.assertEqual(204, r.status_code, "Did not get expected response code")
            self.assertHeaderExists(r, "Atomic-Expires")

            self.log("Create an container in the transaction")
            transaction_headers = {
                'Atomic-Id': transaction_id
            }
            r = self.do_post(headers=transaction_headers)
            self.assertEqual(201, r.status_code, "Did not get expected response code")
            transaction_obj = self.get_location(r)

            self.log("Container is available inside the transaction")
            r = self.do_get(transaction_obj, headers=transaction_headers)
            self.assertEqual(200, r.status_code, "Did not get expected response code")

            self.log("Container not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.assertEqual(404, r.status_code, "Did not get expected response code")

            self.log("Use an invalid transaction ID")
            bad_headers = {
                'Atomic-ID': 'this-is-a-failure'
            }
            r = self.do_post(headers=bad_headers)
            self.assertEqual(409, r.status_code, "Did not get expected response code")

            self.log("Use the bare UUID of a valid transaction ID")
            diff_headers = {
                'Atomic-ID': transaction_id.replace(self.getFedoraBase() + "/" + TestConstants.FCR_TX + "/", "")
            }
            r = self.do_post(headers=diff_headers)
            self.assertEqual(201, r.status_code, "Did not get expected response code")
            second_obj = self.get_location(r)

            self.log("Second container is available inside the transaction")
            r = self.do_get(second_obj, headers=transaction_headers)
            self.assertEqual(200, r.status_code, "Did not get expected response code")

            self.log("Second container not available outside the transaction")
            r = self.do_get(second_obj)
            self.assertEqual(404, r.status_code, "Did not get expected response code")

            self.log("Try to commit with POST")
            r = self.do_post(transaction_id + "/commit")
            self.assertEqual(405, r.status_code, "Did not get expected response code")

            self.log("Commit transaction")
            r = self.do_put(transaction_id + "/commit")
            self.assertEqual(204, r.status_code, "Did not get expected response code")

            self.log("Container is now available outside the transaction")
            r = self.do_get(transaction_obj)
            self.assertEqual(200, r.status_code, "Did not get expected response code")

            self.log("Transaction is no longer available")
            r = self.do_get(transaction_id)
            self.assertEqual(410, r.status_code, "Did not get expected response code")

            self.log("Can't use the transaction anymore")
            r = self.do_post(headers=transaction_headers)
            self.assertEqual(409, r.status_code, "Did not get expected response code")

    @Test
    def doRollbackTest(self):
        tx_provider = self.get_transaction_provider()
        if tx_provider is None:
            self.log("Could not location transaction provider")
            self.log("Skipping test")
        else:
            self.log("Create a transaction")
            r = self.do_post(tx_provider)
            self.assertEqual(201, r.status_code, "Did not get expected response code")
            transaction_id = self.get_location(r)
            self.log("Transaction is {0}".format(transaction_id))

            self.log("Create an container in the transaction")
            transaction_headers = {
                'Atomic-Id': transaction_id
            }
            r = self.do_post(headers=transaction_headers)
            self.assertEqual(201, r.status_code, "Did not get expected response code")
            transaction_obj = self.get_location(r)

            self.log("Container is available inside the transaction")
            r = self.do_get(transaction_obj, headers=transaction_headers)
            self.assertEqual(200, r.status_code, "Did not get expected response code")

            self.log("Container not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.assertEqual(404, r.status_code, "Did not get expected response code")

            self.log("Rollback transaction")
            r = self.do_delete(transaction_id)
            self.assertEqual(204, r.status_code, "Did not get expected response code")

            self.log("Container is still not available outside the transaction")
            r = self.do_get(transaction_obj)
            self.assertEqual(404, r.status_code, "Did not get expected response code")

            self.log("Transaction is no longer available")
            r = self.do_get(transaction_id)
            self.assertEqual(410, r.status_code, "Did not get expected response code")

            self.log("Can't use the transaction anymore")
            r = self.do_post(headers=transaction_headers)
            self.assertEqual(409, r.status_code, "Did not get expected response code")
