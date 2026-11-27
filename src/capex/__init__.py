"""Capacity expansion model (formulation F-0.3 is a superset of F-0.2)."""

FORMULATION_VERSION = "F-0.3"                # fingerprint component: the formulation the code implements (8.10)
ACCEPTED_FORMULATIONS = ("F-0.2", "F-0.3")   # case.yaml formulation_version values the loader reads
DCPF_FORMULATION = "F-0.3"                   # tx.model = dcpf requires this case version
SCHEMA_VERSION = "S-0.1"
