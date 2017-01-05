#!/usr/bin/env python
#
# Copyright 2017 the original author or authors.
#
# Code adapted from https://github.com/choppsv1/netconf
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import structlog
from netconf.constants import Constants as C
from base.commit import Commit
from base.copy_config import CopyConfig
from base.delete_config import DeleteConfig
from base.edit_config import EditConfig
from base.get import Get
from base.get_config import GetConfig
from base.lock import Lock
from base.unlock import UnLock
from base.close_session import CloseSession
from base.kill_session import KillSession
from ext.get_schemas import GetSchemas
from ext.get_schema import GetSchema
from ext.get_voltha import GetVoltha
import netconf.nc_common.error as ncerror
from netconf.nc_common.utils import qmap, ns
from lxml import etree


log = structlog.get_logger()

class RpcFactory:
    instance = None

    def __init__(self):
        pass

    def _get_key(self, namespace, service, name):
        return ''.join([namespace, service, name])

    def get_attribute_value(self, name, attributes):
        for tup in attributes.items():
            if tup[0] == name:
                return tup[1]


    # Parse a request (node is an ElementTree) and return a dictionary
    # TODO:  This parser is specific for a GET/GET SCHEMAS request.  Need to be
    #  it more generic
    def parse_xml_request(self, node):
        request = {}
        if not len(node):
            return request
        for elem in node.iter():
            if elem.tag.find(qmap(C.NC)) != -1:  # found
                elem_name = elem.tag.replace(qmap(C.NC), "")
                if elem_name == 'rpc':
                    request['type'] = 'rpc'
                    request['message_id'] = self.get_attribute_value(
                        'message-id', elem.attrib)
                elif elem_name == 'filter':
                    request['filter'] = self.get_attribute_value('type',
                                                                 elem.attrib)
                else:
                    request[
                        'command'] = elem_name  # attribute is empty for now
            elif elem.tag.find(qmap(C.VOLTHA)) != -1:  # found
                request['namespace'] = ns(C.VOLTHA)
                if request.has_key('class'):
                    request['subclass'] = elem.tag.replace(qmap(C.VOLTHA),"")
                else:
                    request['class'] = elem.tag.replace(qmap(C.VOLTHA), "")
            elif elem.tag.find(qmap(C.NCM)) != -1:  # found
                request['namespace'] = ns(C.NCM)
                elem_name = elem.tag.replace(qmap(C.NCM), "")
                if elem_name == 'get-schema':
                    request['command'] = elem_name
                    request['class'] = elem_name
                elif request.has_key('class'):
                    request['subclass'] = elem_name
                elif elem_name == 'netconf-state':
                    request['command'] = 'get-schemas'
                    request['class'] = elem_name

        return request


    def get_rpc_handler(self, rpc_node, msg, grpc_channel, session,
                        capabilities):
        try:
            # Parse the request into a dictionary
            log.info("rpc-node",
                     node=etree.tostring(rpc_node, pretty_print=True))

            request = self.parse_xml_request(rpc_node)
            if not request:
                log.error("request-bad-format")
                raise ncerror.BadMsg(rpc_node)

            log.info("parsed-request", request=request)

            if not request.has_key('message_id'):
                log.error("request-no-message-id")
                raise ncerror.BadMsg(rpc_node)

            class_handler = self.rpc_class_handlers.get(request['command'],
                                                        None)
            if class_handler is not None:
                return class_handler(request, rpc_node, grpc_channel, session,
                                     capabilities)

            log.error("rpc-not-implemented", rpc=request['command'])

        except ncerror.BadMsg as err:
            log.info('ncerror.BadMsg')
            raise ncerror.BadMsg(rpc_node)

        except Exception as e:
            raise ncerror.ServerException(rpc_node, exception=e)

    rpc_class_handlers = {
        'getvoltha': GetVoltha,
        'get-config': GetConfig,
        'get': Get,
        'get-schemas': GetSchemas,
        'get-schema': GetSchema,
        'edit-config': EditConfig,
        'copy-config': CopyConfig,
        'delete-config': DeleteConfig,
        'commit': Commit,
        'lock': Lock,
        'unlock': UnLock,
        'close-session': CloseSession,
        'kill-session': KillSession
    }


def get_rpc_factory_instance():
    if RpcFactory.instance == None:
        RpcFactory.instance = RpcFactory()
    return RpcFactory.instance
