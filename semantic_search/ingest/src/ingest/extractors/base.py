from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Iterator, List


@dataclass
class ExtractedPage:
    """Représente une page extraite d'un document, avec son numéro, son texte et des métadonnées associées."""
    # Numéro de page (commence à 1)
    page_number: int
    # Contenu textuel extrait de la page
    text: str
    # Métadonnées supplémentaires (ex: type de source, langue, etc.)
    # field(default_factory=dict) permet d'initialiser metadata à un dictionnaire vide par défaut
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Métadonnées standardisées pour faciliter l'indexation
    title: str = ""
    author: str = ""
    creation_date: str = ""
    modification_date: str = ""
    language: str = "fr" 


class Extractor(ABC):
    """Classe de base abstraite pour les extracteurs de documents."""

    # Liste des extensions de fichiers supportées par cet extracteur (ex: [".pdf", ".docx"])
    SUPPORTED_EXTENSIONS: List[str] = []

    # Méthode de classe pour vérifier si l'extracteur peut gérer un fichier donné en fonction de son extension
    # file_path.suffix.lower() permet de comparer l'extension du fichier de manière insensible à la casse
    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        return file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS

    # Méthode abstraite à implémenter par les sous-classes pour extraire le texte d'un fichier et retourner un itérateur de pages extraites
    # Chaque page est représentée par une instance de ExtractedPage.
    @abstractmethod
    def extract(self, file_path: Path) -> Iterator[ExtractedPage]:
        """Extraire le contenu textuel d'un fichier, en renvoyant des objets ExtractedPage."""
        ...
