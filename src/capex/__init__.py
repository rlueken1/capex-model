"""Capacity expansion model (formulation F-0.4 is a superset of F-0.3 and F-0.2)."""

FORMULATION_VERSION = "F-0.4"                          # fingerprint component: the formulation the code implements (8.10)
ACCEPTED_FORMULATIONS = ("F-0.2", "F-0.3", "F-0.4")    # case.yaml formulation_version values the loader reads
DCPF_FORMULATIONS = ("F-0.3", "F-0.4")                 # tx.model = dcpf requires one of these case versions
F04_FORMULATION = "F-0.4"                              # F-0.4 inputs (link_type, tx.dc_links, audit_profile) need this
SCHEMA_VERSION = "S-0.1"
