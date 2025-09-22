"""Document loader for EverNote ENEX export files.

This module provides functionality to securely load and parse EverNote notebook
export files (``.enex`` format) into LangChain Document objects.
"""

import hashlib
import logging
from base64 import b64decode
from pathlib import Path
from time import strptime
from typing import Any, Dict, Iterator, List, Optional, Union

from langchain_core.documents import Document

from langchain_community.document_loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class EverNoteLoader(BaseLoader):
    """Document loader for EverNote ENEX export files.

    Loads EverNote notebook export files (``.enex`` format) into LangChain Documents.
    Extracts plain text content from HTML and preserves note metadata including
    titles, timestamps, and attachments. Uses secure XML parsing to prevent
    vulnerabilities.

    The loader supports two modes:
    - Single document: Concatenates all notes into one Document (default)
    - Multiple documents: Creates separate Documents for each note

    `Instructions for creating ENEX files <https://help.evernote.com/hc/en-us/articles/209005557-Export-notes-and-notebooks-as-ENEX-or-HTML>`__

    Example:

    .. code-block:: python

        from langchain_community.document_loaders import EverNoteLoader

        # Load all notes as a single document
        loader = EverNoteLoader("my_notebook.enex")
        documents = loader.load()

        # Load each note as a separate document:
        # documents = [ document1, document2, ... ]
        loader = EverNoteLoader("my_notebook.enex", load_single_document=False)
        documents = loader.load()

        # Lazy loading for large files
        for doc in loader.lazy_load():
            print(f"Title: {doc.metadata.get('title', 'Untitled')}")
            print(f"Content: {doc.page_content[:100]}...")

    Note:
        Requires the ``lxml`` and ``html2text`` packages to be installed.
        Install with: ``pip install lxml html2text``
    """

    def __init__(self, file_path: Union[str, Path], load_single_document: bool = True):
        """Initialize the EverNote loader.

        Args:
            file_path: Path to the EverNote export file (``.enex`` extension).
            load_single_document: Whether to concatenate all notes into a single
                Document. If ``True``, only the ``source`` metadata is preserved.
                If ``False``, each note becomes a separate Document with its own
                metadata.
        """
        self.file_path = str(file_path)
        self.load_single_document = load_single_document

    def _lazy_load(self) -> Iterator[Document]:
        """Lazily load documents from the EverNote export file.

        Lazy loading allows processing large EverNote files without
        loading everything into memory at once. This method yields Documents
        one by one by parsning the XML. Each document represents a note in the EverNote
        export, containing the note's content as ``page_content`` and metadata including
        ``title``, ``created/updated`` ``timestamps``, and other note attributes.

        Yields:
            Document: A Document object for each note in the export file.
        """
        for note in self._parse_note_xml(self.file_path):
            if note.get("content") is not None:
                yield Document(
                    page_content=note["content"],
                    metadata={
                        **{
                            key: value
                            for key, value in note.items()
                            if key not in ["content", "content-raw", "resource"]
                        },
                        **{"source": self.file_path},
                    },
                )

    def lazy_load(self) -> Iterator[Document]:
        """Load documents from EverNote export file.

        Depending on the ``load_single_document`` setting, either yields individual
        Documents for each note or a single Document containing all notes.

        Yields:
            Document: Either individual note Documents or a single combined Document.
        """
        if not self.load_single_document:
            yield from self._lazy_load()
        else:
            yield Document(
                page_content="".join(
                    [document.page_content for document in self._lazy_load()]
                ),
                metadata={"source": self.file_path},
            )

    @staticmethod
    def _parse_content(content: str) -> str:
        """Parse HTML content from EverNote into plain text.

        Converts HTML content to plain text using the ``html2text`` library.
        Strips whitespace from the result.

        Args:
            content: HTML content string from EverNote.

        Returns:
            Plain text version of the content.

        Raises:
            ImportError: If ``html2text`` is not installed.
        """
        try:
            import html2text

            return html2text.html2text(content).strip()
        except ImportError as e:
            raise ImportError(
                "Could not import `html2text`. Although it is not a required package "
                "to use LangChain, using the EverNote loader requires `html2text`. "
                "Please install `html2text` via `pip install html2text` and try again."
            ) from e

    @staticmethod
    def _parse_resource(resource: list) -> dict:
        """Parse resource elements from EverNote XML.

        Extracts resource information like attachments, images, etc.
        Base64 decodes data elements and generates MD5 hashes.

        Args:
            resource: List of XML elements representing a resource.

        Returns:
            Dictionary containing resource metadata and decoded data.
        """
        rsc_dict: Dict[str, Any] = {}
        for elem in resource:
            if elem.tag == "data":
                # Sometimes elem.text is None
                rsc_dict[elem.tag] = b64decode(elem.text) if elem.text else b""
                rsc_dict["hash"] = hashlib.md5(rsc_dict[elem.tag]).hexdigest()
            else:
                rsc_dict[elem.tag] = elem.text

        return rsc_dict

    @staticmethod
    def _parse_note(note: List, prefix: Optional[str] = None) -> dict:
        """Parse a note element from EverNote XML.

        Extracts note content, metadata, resources, and attributes.
        Handles nested note-attributes recursively with prefixes.

        Args:
            note: List of XML elements representing a note.
            prefix: Optional prefix for nested attribute names.

        Returns:
            Dictionary containing note content and metadata.
        """
        note_dict: Dict[str, Any] = {}
        resources = []

        def add_prefix(element_tag: str) -> str:
            if prefix is None:
                return element_tag
            return f"{prefix}.{element_tag}"

        for elem in note:
            if elem.tag == "content":
                note_dict[elem.tag] = EverNoteLoader._parse_content(elem.text)
                # A copy of original content
                note_dict["content-raw"] = elem.text
            elif elem.tag == "resource":
                resources.append(EverNoteLoader._parse_resource(elem))
            elif elem.tag == "created" or elem.tag == "updated":
                note_dict[elem.tag] = strptime(elem.text, "%Y%m%dT%H%M%SZ")
            elif elem.tag == "note-attributes":
                additional_attributes = EverNoteLoader._parse_note(
                    elem, elem.tag
                )  # Recursively enter the note-attributes tag
                note_dict.update(additional_attributes)
            else:
                note_dict[elem.tag] = elem.text

        if len(resources) > 0:
            note_dict["resource"] = resources

        return {add_prefix(key): value for key, value in note_dict.items()}

    @staticmethod
    def _parse_note_xml(xml_file: str) -> Iterator[Dict[str, Any]]:
        """Parse EverNote XML file securely.

        Uses ``lxml`` with secure parsing configuration to prevent XML vulnerabilities
        including XXE attacks, XML bombs, and malformed XML exploitation.

        Args:
            xml_file: Path to the EverNote export XML file.

        Yields:
            Dictionary containing parsed note data for each note in the file.

        Raises:
            ImportError: If ``lxml`` is not installed.
        """
        try:
            from lxml import etree
        except ImportError as e:
            logger.error(
                "Could not import `lxml`. Although it is not a required package to use "
                "LangChain, using the EverNote loader requires `lxml`. Please install "
                "`lxml` via `pip install lxml` and try again."
            )
            raise e

        context = etree.iterparse(
            xml_file,
            encoding="utf-8",
            resolve_entities=False,  # Prevents XXE attacks
            no_network=True,  # Blocks network-based external entities
            recover=False,  # Avoid parsing invalid/malformed XML
            huge_tree=False,  # Protect against XML Bomb DoS attacks
        )

        for action, elem in context:
            if elem.tag == "note":
                yield EverNoteLoader._parse_note(elem)
