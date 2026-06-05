MSL-Network
===========

|docs| |pypi| |github tests|

MSL-Network uses concurrency and asynchronous programming to transfer data across a network and
it is composed of three objects -- a Network Manager_, Client_\s and Service_\s.

The Network Manager_ allows for multiple Client_\s and Service_\s to connect to it and it links a Client_'s
request to the appropriate Service_ to execute the request and then the Network Manager_ sends the response
from the Service_ back to the Client_.

The Network Manager_ uses concurrency to handle requests from multiple Client_\s such that multiple requests
start, run and complete in overlapping time periods and in no specific order. A Client_ can send requests
synchronously or asynchronously to the Network Manager_ for a Service_ to execute. See
`Concurrency and Asynchronous Programming`_ for more details.

JSON_ is used as the data format to exchange information between a Client_ and a Service_. As such, it is
possible to implement a Client_ or a Service_ in any programming language to connect to the Network Manager_.
See the `JSON Formats`_ section for an overview of the data format. One can even connect to the Network
Manager_ from a terminal to send requests, see `Connecting from a Terminal`_ for more details.

Install
-------
To install MSL-Network run::

   pip install msl-network

Alternatively, using the `MSL Package Manager`_ run::

   msl install network

Dependencies
++++++++++++
* Python 3.8+
* cryptography_
* paramiko_

Documentation
-------------
The documentation for MSL-Network can be found `here <https://msl-network.readthedocs.io/en/stable/>`_.

.. |docs| image:: https://readthedocs.org/projects/msl-network/badge/?version=latest
   :target: https://msl-network.readthedocs.io/en/stable/
   :alt: Documentation Status

.. |pypi| image:: https://badge.fury.io/py/msl-network.svg
   :target: https://badge.fury.io/py/msl-network

.. |github tests| image:: https://github.com/MSLNZ/msl-network/actions/workflows/run-tests.yml/badge.svg
   :target: https://github.com/MSLNZ/msl-network/actions/workflows/run-tests.yml

.. _Manager: https://msl-network.readthedocs.io/en/stable/_api/msl.network.manager.html
.. _Client: https://msl-network.readthedocs.io/en/stable/_api/msl.network.client.html#msl.network.client.Client
.. _Service: https://msl-network.readthedocs.io/en/stable/_api/msl.network.service.html
.. _Concurrency and Asynchronous Programming: https://msl-network.readthedocs.io/en/stable/concurrency_async.html#concurrent-asynchronous
.. _JSON: https://www.json.org/
.. _JSON Formats: https://msl-network.readthedocs.io/en/stable/json_formats.html#json-formats
.. _Connecting from a Terminal: https://msl-network.readthedocs.io/en/stable/terminal_input.html#terminal-input
.. _MSL Package Manager: https://msl-package-manager.readthedocs.io/en/stable/
.. _cryptography: https://cryptography.io/en/stable/
.. _paramiko: https://www.paramiko.org/
