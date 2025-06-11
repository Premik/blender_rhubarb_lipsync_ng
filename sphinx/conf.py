
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = 'Rhubarb Lip Sync NG'
release = '1.6'
# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions: list[str] = ['myst_parser']
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
root_doc = "index"
templates_path = ['templates']
# include_patterns = ["md_temp/**"]
rinoh_documents = [
    dict(
        doc='index',
        target='Rhubarb Lip Sync NG',
        logo='doc/img/RLSP-banner.png',
        author="",
        subtitle=f"For v{release}",
        template="rinoh_template.rts"
        # template='/wrk/dev/rhubarb-lipsync/sphinx/rinoh_template.rts',  # Article Book
    )
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# pip install sphinx-book-theme
html_theme = 'sphinx_book_theme'
html_static_path = ['static']

# -- Options for rinoh output -------------------------------------------------
rinoh_stylesheets = ["rinoh_style.rts"]
