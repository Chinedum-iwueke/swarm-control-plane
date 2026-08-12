"""Quarantined scientific document recovery pipeline."""

from app.ingestion.pipeline import OfflineTesseractOcr, ScientificIngestionPipeline

__all__ = ["OfflineTesseractOcr", "ScientificIngestionPipeline"]
