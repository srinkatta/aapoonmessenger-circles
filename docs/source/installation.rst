aapoonmessenger-circleservice
=============================

You need to install following things before project setup:

Installation
============

Use the package manager pip to install aapoonMessenger-circle Microservice Backend.

.. code-block:: bash

   pip install -r requirements.txt


Usage
=====

Run this to make sure your database in sync with latest database changes.

.. code-block:: bash

    python manage.py migrate

Run this to run the server on Port 8000:

.. code-block:: bash

    python manage.py runserver



Coding Standards:
=================

After successfully running the project, install pre-commit to prevent committing bugs or issues early on and improve codebase quality.

Run this to install pre-commit:

.. code-block:: bash

    pre-commit install


Make sure you're following the same structure for new apps which is already being used for the existing ones. Always create an "api" folder and add the api's related things there(viewsets, serializer, routers).

Make sure you use small functions instead of one messy function or class.
