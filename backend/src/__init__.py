"""
csi_dashboard.src
=================
Core business-logic package for the CSI person-detection backend.

Sub-modules
-----------
config      — hardware / tuning constants (single source of truth)
signal      — raw CSI line parsing and variance-based activity classifier
alerts      — Telegram notification helper
state       — shared mutable application state dataclass
utils       — JSON-safe serialization helpers
"""
