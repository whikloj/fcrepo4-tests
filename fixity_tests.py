#!/bin/env python

import TestConstants
from abstract_fedora_tests import FedoraTests, register_tests, Test
import os.path
import pyjq
import json


@register_tests
class FedoraFixityTests(FedoraTests):

    # Create test objects all inside here for easy of review
    CONTAINER = "/test_fixity"

    # Sha1 fixity result for basic_image.jpg in the resource sub-directory
    FIXITY_RESULT_SHA1 = "dec028a4400b4f7ed80ed1174e65179d6b57a0f2"

    def decode_digest_header(self, header):
        digests = dict()
        for digest in header.split(","):
            (alg, value) = digest.split('=')
            digests[alg] = value
        return digests

    @Test
    def aFixityTest(self):

        self.log("Create a binary")
        headers = {
            'Content-type': 'image/jpeg',
        }
        with open(self.getImagePath(), 'rb') as fp:
            data = fp.read()
            r = self.do_post(self.getBaseUri(), headers=headers, body=data)
            self.assertEqual(201, r.status_code, 'Did not create binary')
            location = self.get_location(r)

        self.log("Get a fixity result")
        headers = {
            'Want-Digest': 'sha'
        }
        r = self.do_head(location, headers=headers)
        self.assertEqual(200, r.status_code, "Can't get the fixity result")
        if 'Digest' in r.headers:
            fixity_results = self.decode_digest_header(r.headers['Digest'])
            if 'sha' in fixity_results.keys():
                self.assertEqual(self.FIXITY_RESULT_SHA1, fixity_results['sha'],
                                 "Fixity result was not a match for expected.")
            else:
                self.fail("No sha digest returned")
        else:
            self.fail("No Digest header returned")
