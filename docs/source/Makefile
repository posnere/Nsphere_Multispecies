# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Custom target for HTML output to docs/ directory
html: prepare-notebooks
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "../" $(SPHINXOPTS) $(O) # Output to ../ (docs/)
	@echo "Build finished. The HTML pages are in ../ (project docs/ directory)."
	@$(MAKE) cleanup-notebooks

# Prepare notebooks for the documentation build
prepare-notebooks:
	@echo "Creating temporary notebook handler script..."
	@echo '#!/usr/bin/env python3' > ./_temp_notebook_handler.py
	@echo '"""' >> ./_temp_notebook_handler.py
	@echo 'Temporary script to copy notebooks from examples directory to examples/notebooks' >> ./_temp_notebook_handler.py
	@echo 'for Sphinx documentation processing.' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'This script is auto-generated during the build process and uses pathlib' >> ./_temp_notebook_handler.py
	@echo 'for cross-platform path handling (Windows, macOS, Linux).' >> ./_temp_notebook_handler.py
	@echo '"""' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'import os' >> ./_temp_notebook_handler.py
	@echo 'import shutil' >> ./_temp_notebook_handler.py
	@echo 'from pathlib import Path' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Use pathlib for cross-platform path handling' >> ./_temp_notebook_handler.py
	@echo 'current_dir = Path(__file__).parent.absolute()' >> ./_temp_notebook_handler.py
	@echo 'examples_dir = (current_dir / ".." / ".." / "examples").resolve()' >> ./_temp_notebook_handler.py
	@echo 'target_dir = (current_dir / "examples" / "notebooks").resolve()' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'print(f"Examples directory: {examples_dir}")' >> ./_temp_notebook_handler.py
	@echo 'print(f"Target directory: {target_dir}")' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Create target directory if it does not exist' >> ./_temp_notebook_handler.py
	@echo 'os.makedirs(target_dir, exist_ok=True)' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Find all .ipynb files in the examples directory' >> ./_temp_notebook_handler.py
	@echo 'notebooks = list(examples_dir.glob("*.ipynb"))' >> ./_temp_notebook_handler.py
	@echo 'print(f"Found {len(notebooks)} notebooks")' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'if not notebooks:' >> ./_temp_notebook_handler.py
	@echo '    print("No notebooks found!")' >> ./_temp_notebook_handler.py
	@echo '    exit(1)' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Copy notebooks' >> ./_temp_notebook_handler.py
	@echo 'for notebook in notebooks:' >> ./_temp_notebook_handler.py
	@echo '    target_file = target_dir / notebook.name' >> ./_temp_notebook_handler.py
	@echo '    shutil.copy2(notebook, target_file)' >> ./_temp_notebook_handler.py
	@echo '    print(f"Copied: {notebook.name}")' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Create toctree index file' >> ./_temp_notebook_handler.py
	@echo 'index_content = []' >> ./_temp_notebook_handler.py
	@echo 'index_content.append(".. toctree::")' >> ./_temp_notebook_handler.py
	@echo 'index_content.append("   :maxdepth: 1")' >> ./_temp_notebook_handler.py
	@echo 'index_content.append("   :caption: Example Notebooks:")' >> ./_temp_notebook_handler.py
	@echo 'index_content.append("")' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'for notebook in notebooks:' >> ./_temp_notebook_handler.py
	@echo '    notebook_name = notebook.stem' >> ./_temp_notebook_handler.py
	@echo '    # Use relative path for cross-platform compatibility' >> ./_temp_notebook_handler.py
	@echo '    index_content.append(f"   notebooks/{notebook_name}")' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo '# Write the index file' >> ./_temp_notebook_handler.py
	@echo 'index_file = current_dir / "examples" / "_notebook_index.rst"' >> ./_temp_notebook_handler.py
	@echo 'os.makedirs(index_file.parent, exist_ok=True)' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'with open(index_file, "w") as f:' >> ./_temp_notebook_handler.py
	@echo '    f.write("\\n".join(index_content))' >> ./_temp_notebook_handler.py
	@echo '' >> ./_temp_notebook_handler.py
	@echo 'print(f"Created index file: {index_file}")' >> ./_temp_notebook_handler.py
	@chmod +x ./_temp_notebook_handler.py
	@echo "Running notebook handler script..."
	@python3 ./_temp_notebook_handler.py
	@echo "Notebooks prepared for build."

# Clean up temporary notebooks after build
cleanup-notebooks:
	@echo "Cleaning up temporary notebooks and handler script..."
	@rm -rf ./examples/notebooks ./_temp_notebook_handler.py ./examples/_notebook_index.rst
	@echo "Temporary files cleaned."

.PHONY: help Makefile html clean

clean:
	@echo "Cleaning build directory ($(BUILDDIR)) and Sphinx HTML output from ../docs/..."
	rm -rf $(BUILDDIR)
	# Remove generated HTML output from the parent (docs/) directory
	# List specific generated directories known from Sphinx output structure:
	rm -rf ../_static ../c_api ../examples ../python_api ../usage ../user_guide ../_sources ../_modules ../command_line ../data_flow
	# List specific generated files known from Sphinx output structure:
	rm -f ../index.html ../genindex.html ../py-modindex.html ../search.html ../searchindex.js ../objects.inv .buildinfo
	# Add rm -f ../<any_other_top_level_files>.html if Sphinx creates others
	@echo "Clean complete."

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
