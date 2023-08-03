import os
import sys

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "aapoonmessenger-circles"
copyright = "2023, Praveen Gouda"
author = "Praveen Gouda"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("circle_service"))

# - Add extensions to support the Django-specific documentation:

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # For parsing Google-style docstrings
    "sphinx.ext.viewcode",  # For linking to source code
]

# Add the following line to specify the master document:
master_doc = "index"

# Set the source file suffix for Sphinx to recognize .rst files:
source_suffix = ".rst"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
