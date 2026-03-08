# SAM はソースを一時ディレクトリにコピーして make を実行するため、ARTIFACTS_DIR からプロジェクトルートを導く。
# ARTIFACTS_DIR は .../halstela/.aws-sam/build/SharedLayer の形式なので、.aws-sam より前を取る。
REPO_ROOT := $(shell echo '$(ARTIFACTS_DIR)' | sed 's|/.aws-sam/build/SharedLayer.*||')

# プロジェクトは Python 3.12 必須のため、uv でインストールする（システム pip は 3.11 のことがある）。
build-SharedLayer:
	cd "$(REPO_ROOT)" && uv pip install . -t "$(ARTIFACTS_DIR)/python/" --quiet
