# SAM はソースを一時ディレクトリにコピーして make を実行するため、ARTIFACTS_DIR からプロジェクトルートを導く。
# ARTIFACTS_DIR は .../halstela/.aws-sam/build/SharedLayer の形式なので、.aws-sam より前を取る。
REPO_ROOT := $(shell echo '$(ARTIFACTS_DIR)' | sed 's|/.aws-sam/build/SharedLayer.*||')

# プロジェクトは Python 3.12 必須のため、uv でインストールする（システム pip は 3.11 のことがある）。
# Lambda は arm64 Linux で動くため、ローカル（macOS 等）でビルドしても Lambda 向けの
# ネイティブ拡張（cryptography 等）を取得できるよう --python-platform / --python-version を指定する。
# これを省くとホスト用の .so が入り、Lambda で "invalid ELF header" になる。
build-SharedLayer:
	cd "$(REPO_ROOT)" && uv pip install . \
		--python-platform aarch64-manylinux2014 \
		--python-version 3.12 \
		--target "$(ARTIFACTS_DIR)/python/" --quiet
