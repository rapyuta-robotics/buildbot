# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import json
from urlparse import urlparse

from twisted.internet import defer
from twisted.python import log

from buildbot.process.results import SUCCESS
from buildbot.reporters import http
from buildbot.plugins import changes

import urllib2
import urllib
import base64
import os

# Magic words understood by Butbucket REST API
BITBUCKET_INPROGRESS = 'INPROGRESS'
BITBUCKET_SUCCESSFUL = 'SUCCESSFUL'
BITBUCKET_FAILED = 'FAILED'

_BASE_URL = 'https://api.bitbucket.org/2.0/repositories'
_OAUTH_URL = 'https://bitbucket.org/site/oauth2/access_token'
_GET_TOKEN_DATA = {
    'grant_type': 'client_credentials'
}


class BitbucketStatusPush(http.HttpStatusPushBase):
    name = "BitbucketStatusPush"

    def _postToBuildStatus(self, owner, repo, revision, status, key, url, description=""):
        """Call bitbucket build status API"""
        query_url = os.path.join(_BASE_URL, owner, repo, "commit", revision, "statuses", "build")
        body = {"state": status, "key": key, "url": url,
                "description": description}
        data = urllib.urlencode(body)
        request = urllib2.Request(query_url, data)
        print("username: " + self._username)
        print("password: " + self._password)
        base64string = base64.b64encode('%s:%s' % (self._username, self._password))
        request.add_header("Authorization", "Basic %s" % base64string)
        response = urllib2.urlopen(request)
        return 0

    @defer.inlineCallbacks
    def reconfigService(self, username, password,
                        base_url=_BASE_URL,
                        oauth_url=_OAUTH_URL,
                        **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self._base_url = base_url
        self._oauth_url = oauth_url
        self._username = username
        self._password = password

    @defer.inlineCallbacks
    def send(self, build):
        # Our fork of buldbot doesn't support the requests library. (conflicts with twistd) But in
        # buildbot/buildbot, the person who developed this reporter used requests under the hood,
        # I am openning an issue with this on their website. For now I modified his code
        # to use the authentication method used before.
        print("Sending BB API: kenliao")
        results = build['results']

        if build['complete']:
            status = BITBUCKET_SUCCESSFUL if results == SUCCESS else BITBUCKET_FAILED
        else:
            status = BITBUCKET_INPROGRESS

        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']
            print("Sending SHA:" + sha)
            owner, repo = self.get_owner_and_repo(sourcestamp['repository'])
            # oauth_request = yield self.session.post(self._oauth_url,
            #                                         auth=self._auth,
            #                                         data=_GET_TOKEN_DATA)
            # if oauth_request.status_code == 200:
            #     token = json.loads(oauth_request.content)['access_token']
            # else:
            #     token = ''

            # self.session.headers.update({'Authorization': 'Bearer ' + token})

            # bitbucket_uri = '/'.join([self._base_url, owner, repo, 'commit', sha, 'statuses', 'build'])

            # response = yield self.session.post(bitbucket_uri, json=body)
            # if response.status_code != 201:
            #     log.msg("%s: unable to upload Bitbucket status: %s" %
            #             (response.status_code, response.content))
            repo_slug = owner + "/" + repo
            print("lomis:repo_slug: " + repo_slug)
            print("lomis:sha: " + sha)
            print("lomis:status" + status)
            print("lomis: key" + build['builder']['name'])
            #callStatus = apiWrapper.postCommitBuildStatus(repo_slug, sha, status,
            #    build['builder']['name'], build.get('url', "www.foo.com"))
            self._postToBuildStatus(owner, repo, sha, status, build['builder']['name'],
                                    build.get('url', "www.foo.com")) #url can't be empty



    @staticmethod
    def get_owner_and_repo(repourl):
        """
        Takes a git repository URL from Bitbucket and tries to determine the owner and repository name
        :param repourl: Bitbucket git repo in the form of
                    git@bitbucket.com:OWNER/REPONAME.git
                    https://bitbucket.com/OWNER/REPONAME.git
                    ssh://git@bitbucket.com/OWNER/REPONAME.git
        :return: owner, repo: The owner of the repository and the repository name
        """
        parsed = urlparse(repourl)

        if parsed.scheme:
            path = parsed.path[1:]
        else:
            # we assume git@host:owner/repo.git here
            path = parsed.path.split(':', 1)[-1]

        if path.endswith('.git'):
            path = path[:-4]

        parts = path.split('/')

        assert len(parts) == 2, 'OWNER/REPONAME is expected'

        return parts
