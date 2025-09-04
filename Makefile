.PHONY: vvs-setup vvs-provision vvs-smoke vvs-clean-env

vvs-setup:
	@bash scripts/setup_vvs.sh

vvs-provision:
	@PROJECT_ID=${PROJECT_ID:?} LOCATION=${LOCATION:-us-central1} \
	python3 scripts/provision_vvs.py

vvs-smoke:
	@PROJECT_ID=${PROJECT_ID:?} LOCATION=${LOCATION:-us-central1} \
	VVS_INDEX=${VVS_INDEX:?} VVS_ENDPOINT=${VVS_ENDPOINT:?} \
	python3 scripts/vvs_smoketest.py

vvs-clean-env:
	@rm -f .env.vvs
	@echo "Removed .env.vvs"