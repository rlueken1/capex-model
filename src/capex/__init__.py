"""Capacity expansion model (formulation F-0.3 is a superset of F-0.2)."""

FORMULATION_VERSION = "F-0.2"                # fingerprint component; unchanged so T1-T4 fingerprints stay equal (7.4a.9)
ACCEPTED_FORMULATIONS = ("F-0.2", "F-0.3")   # case.yaml formulation_version values the loader reads
DCPF_FORMULATION = "F-0.3"                   # tx.model = dcpf requires this case version
SCHEMA_VERSION = "S-0.1"
