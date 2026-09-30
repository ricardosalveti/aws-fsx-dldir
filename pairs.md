# Download collisions on FSx: raw evidence

Each block: one file, every runner that reported a checksum problem on it within 30 s, with the runner's instance id, its hostname (= client IP in the VPC) and the raw job log lines. `do_fetch Started/Succeeded/Failed` lines are BitBake task events; the lock is taken inside the task.

# A. Cross-host collisions: two or more hosts corrupt the same download at the same time

## A1. 2026-09-11T15:20:09Z — robotics-sdk — https://files.pythonhosted.org/packages/source/j/jinja2/jinja2-3.1.6.tar.gz

- recipe/task: `python3-jinja2-native-3.1.6-r0`, storage `/efsx`, run 34538407155 attempt 2
- runner `i-03744bef0c0946172` host `ip-10-185-117-172` job 103311047189 (build-pr / iq-8275-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-00df8fa976000516c` host `ip-10-185-112-182` job 103311047287 (build-pr / iq-9075-evk/qcom-robotics-distro_full_linux-qcom-, failure): first checksum warning at +22 ms

```
15:20:09.7198  976000516c ip-10-185-112-182   NOTE: recipe python3-jinja2-native-3.1.6-r0: task do_fetch: Started
15:20:09.7228  f0c0946172 ip-10-185-117-172   NOTE: recipe python3-jinja2-native-3.1.6-r0: task do_fetch: Started
15:20:09.8990  f0c0946172 ip-10-185-117-172   WARNING: python3-jinja2-native-3.1.6-r0 do_fetch: Checksum failure encountered with download of https://files.pythonhosted.org/packages/source/j/jinja2/jinja2-3.1.6.tar.gz;downloadfilename=jinja2-3.1.6.tar.gz - will attempt other sources if available
15:20:09.9213  976000516c ip-10-185-112-182   WARNING: python3-jinja2-native-3.1.6-r0 do_fetch: Checksum failure encountered with download of https://files.pythonhosted.org/packages/source/j/jinja2/jinja2-3.1.6.tar.gz;downloadfilename=jinja2-3.1.6.tar.gz - will attempt other sources if available
15:20:10.7742  976000516c ip-10-185-112-182   WARNING: python3-jinja2-native-3.1.6-r0 do_fetch: Checksum mismatch for local file /downloads/jinja2-3.1.6.tar.gz
15:20:10.7743  976000516c ip-10-185-112-182   WARNING: python3-jinja2-native-3.1.6-r0 do_fetch: Renaming /downloads/jinja2-3.1.6.tar.gz to /downloads/jinja2-3.1.6.tar.gz_bad-checksum_e8cf3321ee743892208bda63b6e976b4b9d65114e926934b62968e0cae8460fb
15:20:10.7787  976000516c ip-10-185-112-182   ERROR: python3-jinja2-native-3.1.6-r0 do_fetch: Checksum failure fetching https://files.pythonhosted.org/packages/source/j/jinja2/jinja2-3.1.6.tar.gz;downloadfilename=jinja2-3.1.6.tar.gz
15:20:10.7793  976000516c ip-10-185-112-182   ERROR: python3-jinja2-native-3.1.6-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/jinja2-3.1.6.tar.gz\' has sha256 checksum \'e8cf3321ee743892208bda63b6e976b4b9d65114e926934b62968e0cae8460fb\' when \'0137fb05990d35f12
15:20:10.7806  976000516c ip-10-185-112-182   NOTE: recipe python3-jinja2-native-3.1.6-r0: task do_fetch: Failed
15:20:11.3907  f0c0946172 ip-10-185-117-172   NOTE: recipe python3-jinja2-native-3.1.6-r0: task do_fetch: Succeeded
```

## A2. 2026-09-12T06:03:17Z — robotics-sdk — crate://crates.io/portable-atomic-util/0.2.7

- recipe/task: `cargo-c-native-0.10.25+cargo-0.99.0-r0`, storage `/efsx`, run 34538407155 attempt 4
- runner `i-082b5f65413b9bb8e` host `ip-10-185-126-77` job 103507436801 (build-pr / iq-8275-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-04f94f58c3d2efc62` host `ip-10-185-117-77` job 103507436820 (build-pr / iq-9075-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +27 ms

```
06:03:06.8443  8c3d2efc62 ip-10-185-117-77    NOTE: recipe cargo-c-native-0.10.25+cargo-0.99.0-r0: task do_fetch: Started
06:03:08.0906  5413b9bb8e ip-10-185-126-77    NOTE: recipe cargo-c-native-0.10.25+cargo-0.99.0-r0: task do_fetch: Started
06:03:17.6018  5413b9bb8e ip-10-185-126-77    WARNING: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/portable-atomic-util/0.2.7 - will attempt other sources if available
06:03:17.6296  8c3d2efc62 ip-10-185-117-77    WARNING: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/portable-atomic-util/0.2.7 - will attempt other sources if available
06:03:18.6267  8c3d2efc62 ip-10-185-117-77    WARNING: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Checksum mismatch for local file /downloads/portable-atomic-util-0.2.7.crate
06:03:18.6277  8c3d2efc62 ip-10-185-117-77    WARNING: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Renaming /downloads/portable-atomic-util-0.2.7.crate to /downloads/portable-atomic-util-0.2.7.crate_bad-checksum_ce18b0f357f7a6ef7eb87ee20096001bbaecf4d6fb6f1faf1484e596eba6e5cb
06:03:18.6347  8c3d2efc62 ip-10-185-117-77    ERROR: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Checksum failure fetching crate://crates.io/portable-atomic-util/0.2.7
06:03:18.6434  5413b9bb8e ip-10-185-126-77    NOTE: recipe cargo-c-native-0.10.25+cargo-0.99.0-r0: task do_fetch: Failed
06:03:18.6553  8c3d2efc62 ip-10-185-117-77    ERROR: cargo-c-native-0.10.25+cargo-0.99.0-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/portable-atomic-util-0.2.7.crate\' has sha256 checksum \'ce18b0f357f7a6ef7eb87ee20096001bbaecf4d6fb6f1faf1484e596eba6e5cb\' whe
06:03:18.6559  8c3d2efc62 ip-10-185-117-77    NOTE: recipe cargo-c-native-0.10.25+cargo-0.99.0-r0: task do_fetch: Failed
```

## A3. 2026-09-13T18:47:26Z — robotics-sdk — https://files.pythonhosted.org/packages/source/s/setuptools_rust/setuptools_rust-1.13.0.tar.gz

- recipe/task: `python3-setuptools-rust-native-1.13.0-r0`, storage `/efsx`, run 34538407155 attempt 5
- runner `i-06a80327d5ee05ba5` host `ip-10-185-125-90` job 103764395295 (build-pr / iq-8275-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-052827f0cd22f1940` host `ip-10-185-119-170` job 103764395303 (build-pr / iq-9075-evk/qcom-robotics-distro_base_linux-qcom-, failure): first checksum warning at +306 ms

```
18:47:24.3918  0cd22f1940 ip-10-185-119-170   NOTE: recipe python3-setuptools-rust-native-1.13.0-r0: task do_fetch: Started
18:47:24.4186  7d5ee05ba5 ip-10-185-125-90    NOTE: recipe python3-setuptools-rust-native-1.13.0-r0: task do_fetch: Started
18:47:26.8198  7d5ee05ba5 ip-10-185-125-90    WARNING: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Checksum failure encountered with download of https://files.pythonhosted.org/packages/source/s/setuptools_rust/setuptools_rust-1.13.0.tar.gz;downloadfilename=setuptools_rust-1.13.0.tar.gz - will attem
18:47:27.1262  0cd22f1940 ip-10-185-119-170   WARNING: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Checksum failure encountered with download of https://files.pythonhosted.org/packages/source/s/setuptools_rust/setuptools_rust-1.13.0.tar.gz;downloadfilename=setuptools_rust-1.13.0.tar.gz - will attem
18:47:28.0943  0cd22f1940 ip-10-185-119-170   NOTE: recipe python3-setuptools-rust-native-1.13.0-r0: task do_fetch: Failed
18:47:28.2707  7d5ee05ba5 ip-10-185-125-90    WARNING: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Checksum mismatch for local file /downloads/setuptools_rust-1.13.0.tar.gz
18:47:28.2710  7d5ee05ba5 ip-10-185-125-90    WARNING: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Renaming /downloads/setuptools_rust-1.13.0.tar.gz to /downloads/setuptools_rust-1.13.0.tar.gz_bad-checksum_0b47c975b4dcb093df1ab689ed8ad03c3078211adfab2f3dc8729bea45f4ecc1
18:47:28.3881  7d5ee05ba5 ip-10-185-125-90    ERROR: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Checksum failure fetching https://files.pythonhosted.org/packages/source/s/setuptools_rust/setuptools_rust-1.13.0.tar.gz;downloadfilename=setuptools_rust-1.13.0.tar.gz
18:47:28.5515  7d5ee05ba5 ip-10-185-125-90    ERROR: python3-setuptools-rust-native-1.13.0-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/setuptools_rust-1.13.0.tar.gz\' has sha256 checksum \'0b47c975b4dcb093df1ab689ed8ad03c3078211adfab2f3dc8729bea45f4ecc1\' when
18:47:28.5522  7d5ee05ba5 ip-10-185-125-90    NOTE: recipe python3-setuptools-rust-native-1.13.0-r0: task do_fetch: Failed
```

## A4. 2026-09-13T18:57:57Z — robotics-sdk — crate://crates.io/glam/0.27.0

- recipe/task: `librsvg-2.62.3-r0`, storage `/efsx`, run 34538407155 attempt 5
- runner `i-0bc58763e4d81e819` host `ip-10-185-119-89` job 103764395288 (build-pr / iq-8275-evk/qcom-robotics-distro_full_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-01526cd2f50406ef6` host `ip-10-185-127-177` job 103764395300 (build-pr / iq-9075-evk/qcom-robotics-distro_full_linux-qcom-, cancelled): first checksum warning at +49 ms

```
18:53:13.5348  2f50406ef6 ip-10-185-127-177   NOTE: recipe librsvg-2.62.3-r0: task do_fetch: Started
18:56:30.7449  3e4d81e819 ip-10-185-119-89    NOTE: recipe librsvg-2.62.3-r0: task do_fetch: Started
18:57:57.9535  3e4d81e819 ip-10-185-119-89    WARNING: librsvg-2.62.3-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/glam/0.27.0 - will attempt other sources if available
18:57:58.0036  2f50406ef6 ip-10-185-127-177   WARNING: librsvg-2.62.3-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/glam/0.27.0 - will attempt other sources if available
18:57:59.1842  3e4d81e819 ip-10-185-119-89    NOTE: recipe librsvg-2.62.3-r0: task do_fetch: Failed
18:57:59.4029  2f50406ef6 ip-10-185-127-177   WARNING: librsvg-2.62.3-r0 do_fetch: Checksum mismatch for local file /downloads/glam-0.27.0.crate
18:57:59.4030  2f50406ef6 ip-10-185-127-177   WARNING: librsvg-2.62.3-r0 do_fetch: Renaming /downloads/glam-0.27.0.crate to /downloads/glam-0.27.0.crate_bad-checksum_02598891d0107f351d1b52116b02804e3f66efacf20ea2d455a4518bfd8ef3b3
18:57:59.5659  2f50406ef6 ip-10-185-127-177   ERROR: librsvg-2.62.3-r0 do_fetch: Checksum failure fetching crate://crates.io/glam/0.27.0
18:57:59.7178  2f50406ef6 ip-10-185-127-177   ERROR: librsvg-2.62.3-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/glam-0.27.0.crate\' has sha256 checksum \'02598891d0107f351d1b52116b02804e3f66efacf20ea2d455a4518bfd8ef3b3\' when \'9e05e7e6723e3455f4818c7b26e85543
18:57:59.7182  2f50406ef6 ip-10-185-127-177   NOTE: recipe librsvg-2.62.3-r0: task do_fetch: Failed
```

## A5. 2026-09-15T02:16:16Z — robotics-sdk — crate://crates.io/untrusted/0.9.0

- recipe/task: `python3-maturin-native-1.15.0-r0`, storage `/efsx`, run 34916088202 attempt 2
- runner `i-047416ccba37a7730` host `ip-10-185-126-59` job 104224760832 (build-pr / iq-8275-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-0f31887f68d949cb6` host `ip-10-185-122-200` job 104224761035 (build-pr / iq-9075-evk/qcom-robotics-distro_base_linux-qcom-, cancelled): first checksum warning at +11 ms

```
02:15:27.8963  f68d949cb6 ip-10-185-122-200   NOTE: recipe python3-maturin-native-1.15.0-r0: task do_fetch: Started
02:15:28.1938  cba37a7730 ip-10-185-126-59    NOTE: recipe python3-maturin-native-1.15.0-r0: task do_fetch: Started
02:16:16.4199  cba37a7730 ip-10-185-126-59    WARNING: python3-maturin-native-1.15.0-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/untrusted/0.9.0 - will attempt other sources if available
02:16:16.4305  f68d949cb6 ip-10-185-122-200   WARNING: python3-maturin-native-1.15.0-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/untrusted/0.9.0 - will attempt other sources if available
02:16:17.4485  f68d949cb6 ip-10-185-122-200   WARNING: python3-maturin-native-1.15.0-r0 do_fetch: Checksum mismatch for local file /downloads/untrusted-0.9.0.crate
02:16:17.4494  f68d949cb6 ip-10-185-122-200   WARNING: python3-maturin-native-1.15.0-r0 do_fetch: Renaming /downloads/untrusted-0.9.0.crate to /downloads/untrusted-0.9.0.crate_bad-checksum_5405d394dd789af13a6328310e15076bc341c2d9dd5ea6f09f15f4fbc712619f
02:16:17.4580  f68d949cb6 ip-10-185-122-200   ERROR: python3-maturin-native-1.15.0-r0 do_fetch: Checksum failure fetching crate://crates.io/untrusted/0.9.0
02:16:17.4654  f68d949cb6 ip-10-185-122-200   ERROR: python3-maturin-native-1.15.0-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/untrusted-0.9.0.crate\' has sha256 checksum \'5405d394dd789af13a6328310e15076bc341c2d9dd5ea6f09f15f4fbc712619f\' when \'8ecb6da28b8a3
02:16:17.4671  f68d949cb6 ip-10-185-122-200   NOTE: recipe python3-maturin-native-1.15.0-r0: task do_fetch: Failed
02:16:18.1149  cba37a7730 ip-10-185-126-59    NOTE: recipe python3-maturin-native-1.15.0-r0: task do_fetch: Failed
```

## A6. 2026-09-24T00:47:03Z — robotics-sdk — crate://crates.io/endian-type/0.1.2

- recipe/task: `aardvark-dns-1.17.1-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-0a37dd688f5250e8a` host `ip-10-185-121-136` job 107441032519 (build-pr / iq-8275-evk/qcom-robotics-distro_full_linux-qcom-, cancelled): first checksum warning at +0 ms
- runner `i-0b2eb3ecd5d7ab8f4` host `ip-10-185-117-57` job 107441032468 (build-pr / iq-8275-evk/qcom-robotics-distro_base_linux-qcom-, failure): first checksum warning at +26 ms

```
00:46:50.2849  cd5d7ab8f4 ip-10-185-117-57    NOTE: recipe aardvark-dns-1.17.1-r0: task do_fetch: Started
00:46:56.5330  88f5250e8a ip-10-185-121-136   NOTE: recipe aardvark-dns-1.17.1-r0: task do_fetch: Started
00:47:03.6537  88f5250e8a ip-10-185-121-136   WARNING: aardvark-dns-1.17.1-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/endian-type/0.1.2 - will attempt other sources if available
00:47:03.6804  cd5d7ab8f4 ip-10-185-117-57    WARNING: aardvark-dns-1.17.1-r0 do_fetch: Checksum mismatch for local file /downloads/endian-type-0.1.2.crate
00:47:03.6806  cd5d7ab8f4 ip-10-185-117-57    WARNING: aardvark-dns-1.17.1-r0 do_fetch: Renaming /downloads/endian-type-0.1.2.crate to /downloads/endian-type-0.1.2.crate_bad-checksum_f3e43768bec229ad4567bca3e86146a3a6919648b8991d545e3a97c1f7c239b9
00:47:03.7448  cd5d7ab8f4 ip-10-185-117-57    WARNING: aardvark-dns-1.17.1-r0 do_fetch: Checksum failure encountered with download of crate://crates.io/endian-type/0.1.2 - will attempt other sources if available
00:47:04.8842  88f5250e8a ip-10-185-121-136   WARNING: aardvark-dns-1.17.1-r0 do_fetch: Checksum mismatch for local file /downloads/endian-type-0.1.2.crate
00:47:04.8844  88f5250e8a ip-10-185-121-136   WARNING: aardvark-dns-1.17.1-r0 do_fetch: Renaming /downloads/endian-type-0.1.2.crate to /downloads/endian-type-0.1.2.crate_bad-checksum_5accc8db88f1d0e88bb51d47a3c4fa06bde96bb69be77ef0e12a364745f1c744
00:47:04.9530  cd5d7ab8f4 ip-10-185-117-57    NOTE: recipe aardvark-dns-1.17.1-r0: task do_fetch: Failed
00:47:05.0433  88f5250e8a ip-10-185-121-136   ERROR: aardvark-dns-1.17.1-r0 do_fetch: Checksum failure fetching crate://crates.io/endian-type/0.1.2
00:47:05.0965  88f5250e8a ip-10-185-121-136   ERROR: aardvark-dns-1.17.1-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/endian-type-0.1.2.crate\' has sha256 checksum \'5accc8db88f1d0e88bb51d47a3c4fa06bde96bb69be77ef0e12a364745f1c744\' when \'c34f04666d835ff5d62e0
00:47:05.1083  88f5250e8a ip-10-185-121-136   NOTE: recipe aardvark-dns-1.17.1-r0: task do_fetch: Failed
```

## A7. 2026-09-24T00:51:03Z — robotics-sdk — gomod://github.com/anchore/go-struct-converter

- recipe/task: `docker-compose-5.1.4-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-04ce780dae001b5fc` host `ip-10-185-116-32` job 107441032610 (build-pr / iq-9075-evk/debug_full_linux-qcom-next, cancelled): first checksum warning at +0 ms
- runner `i-03e3de1e4d66eff15` host `ip-10-185-119-122` job 107441032512 (build-pr / iq-8275-evk/debug_full_linux-qcom-next, cancelled): first checksum warning at +9 ms

```
00:50:50.1893  e4d66eff15 ip-10-185-119-122   NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Started
00:50:55.6908  dae001b5fc ip-10-185-116-32    NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Started
00:51:03.8504  dae001b5fc ip-10-185-116-32    WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/anchore/go-struct-converter;version=v0.1.0;sha256sum=d59da72ec5a33286bf91e47055e3a526474f9ee2755735be7221dad0540dc88c - will attempt other sources if av
00:51:03.8591  e4d66eff15 ip-10-185-119-122   WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/anchore/go-struct-converter;version=v0.1.0;sha256sum=d59da72ec5a33286bf91e47055e3a526474f9ee2755735be7221dad0540dc88c - will attempt other sources if av
00:51:15.4959  e4d66eff15 ip-10-185-119-122   WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum mismatch for local file /downloads/github.com.anchore.go-struct-converter@v0.1.0.zip
00:51:15.4963  e4d66eff15 ip-10-185-119-122   WARNING: docker-compose-5.1.4-r0 do_fetch: Renaming /downloads/github.com.anchore.go-struct-converter@v0.1.0.zip to /downloads/github.com.anchore.go-struct-converter@v0.1.0.zip_bad-checksum_0de3d097a8c9be4692b5838fe98f8363f2d7208802b316c38dceb25ab1276275
00:51:15.7880  e4d66eff15 ip-10-185-119-122   ERROR: docker-compose-5.1.4-r0 do_fetch: Checksum failure fetching gomod://github.com/anchore/go-struct-converter;version=v0.1.0;sha256sum=d59da72ec5a33286bf91e47055e3a526474f9ee2755735be7221dad0540dc88c
00:51:15.7918  e4d66eff15 ip-10-185-119-122   ERROR: docker-compose-5.1.4-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/github.com.anchore.go-struct-converter@v0.1.0.zip\' has sha256 checksum \'0de3d097a8c9be4692b5838fe98f8363f2d7208802b316c38dceb25ab1276275\' w
00:51:15.8030  e4d66eff15 ip-10-185-119-122   NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Failed
00:51:16.3573  dae001b5fc ip-10-185-116-32    ERROR: docker-compose-5.1.4-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/github.com/anchore/go-struct-converter/%40v/v0.1.0.zip'. Checksum mismatch!
00:51:16.4295  dae001b5fc ip-10-185-116-32    NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Failed
```

## A8. 2026-09-24T00:51:47Z — robotics-sdk — gomod://github.com/aws/aws-sdk-go-v2/feature/s3/manager

- recipe/task: `docker-compose-5.1.4-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-0c8c3aae032732d06` host `ip-10-185-125-161` job 107441032459 (build-pr / iq-8275-evk/debug_base_linux-qcom-next, cancelled): first checksum warning at +0 ms
- runner `i-0385f5ec2e2685426` host `ip-10-185-118-182` job 107441032550 (build-pr / iq-9075-evk/debug_base_linux-qcom-next, cancelled): first checksum warning at +128 ms

```
00:50:32.6056  c2e2685426 ip-10-185-118-182   NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Started
00:50:46.4625  e032732d06 ip-10-185-125-161   NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Started
00:51:47.0069  e032732d06 ip-10-185-125-161   WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/aws/aws-sdk-go-v2/feature/s3/manager;version=v1.17.10;sha256sum=e4ff6e115f4d1261ef0a1d503c100a161e48f9632ee79ab2ef6b818175e502a2 - will attempt other so
00:51:47.1352  c2e2685426 ip-10-185-118-182   WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/aws/aws-sdk-go-v2/feature/s3/manager;version=v1.17.10;sha256sum=e4ff6e115f4d1261ef0a1d503c100a161e48f9632ee79ab2ef6b818175e502a2 - will attempt other so
00:51:49.9070  e032732d06 ip-10-185-125-161   WARNING: docker-compose-5.1.4-r0 do_fetch: Checksum mismatch for local file /downloads/github.com.aws.aws-sdk-go-v2.feature.s3.manager@v1.17.10.zip
00:51:49.9084  e032732d06 ip-10-185-125-161   WARNING: docker-compose-5.1.4-r0 do_fetch: Renaming /downloads/github.com.aws.aws-sdk-go-v2.feature.s3.manager@v1.17.10.zip to /downloads/github.com.aws.aws-sdk-go-v2.feature.s3.manager@v1.17.10.zip_bad-checksum_acf708a9a615bc024f7753ebda92e311a657b589d266aa7a
00:51:49.9711  e032732d06 ip-10-185-125-161   ERROR: docker-compose-5.1.4-r0 do_fetch: Checksum failure fetching gomod://github.com/aws/aws-sdk-go-v2/feature/s3/manager;version=v1.17.10;sha256sum=e4ff6e115f4d1261ef0a1d503c100a161e48f9632ee79ab2ef6b818175e502a2
00:51:49.9911  e032732d06 ip-10-185-125-161   ERROR: docker-compose-5.1.4-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/github.com.aws.aws-sdk-go-v2.feature.s3.manager@v1.17.10.zip\' has sha256 checksum \'acf708a9a615bc024f7753ebda92e311a657b589d266aa7ae2c651153
00:51:49.9957  e032732d06 ip-10-185-125-161   NOTE: recipe docker-compose-5.1.4-r0: task do_fetch: Failed
```

## A9. 2026-09-24T00:52:01Z — robotics-sdk — gomod://github.com/cenkalti/backoff/v5

- recipe/task: `nerdctl-v2.3.1-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-0385f5ec2e2685426` host `ip-10-185-118-182` job 107441032550 (build-pr / iq-9075-evk/debug_base_linux-qcom-next, cancelled): first checksum warning at +0 ms
- runner `i-0c8c3aae032732d06` host `ip-10-185-125-161` job 107441032459 (build-pr / iq-8275-evk/debug_base_linux-qcom-next, cancelled): first checksum warning at +9 ms

```
00:50:43.6345  c2e2685426 ip-10-185-118-182   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:50:59.2524  e032732d06 ip-10-185-125-161   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:52:01.3594  c2e2685426 ip-10-185-118-182   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/cenkalti/backoff/v5;version=v5.0.3;sha256sum=58e4d9014277bc1c5c7ab64539137923964cc3920303a4f771d02a532939bedb - will attempt other sources if available
00:52:01.3696  e032732d06 ip-10-185-125-161   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/cenkalti/backoff/v5;version=v5.0.3;sha256sum=58e4d9014277bc1c5c7ab64539137923964cc3920303a4f771d02a532939bedb - will attempt other sources if available
00:52:02.1937  c2e2685426 ip-10-185-118-182   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum mismatch for local file /downloads/github.com.cenkalti.backoff.v5@v5.0.3.zip
00:52:02.1938  c2e2685426 ip-10-185-118-182   WARNING: nerdctl-v2.3.1-r0 do_fetch: Renaming /downloads/github.com.cenkalti.backoff.v5@v5.0.3.zip to /downloads/github.com.cenkalti.backoff.v5@v5.0.3.zip_bad-checksum_a9d1a38e5cbf725ccc503febff019fda32deaded92a514a4b613e106ba515a42
00:52:02.2105  c2e2685426 ip-10-185-118-182   ERROR: nerdctl-v2.3.1-r0 do_fetch: Checksum failure fetching gomod://github.com/cenkalti/backoff/v5;version=v5.0.3;sha256sum=58e4d9014277bc1c5c7ab64539137923964cc3920303a4f771d02a532939bedb
00:52:02.2125  c2e2685426 ip-10-185-118-182   ERROR: nerdctl-v2.3.1-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/github.com.cenkalti.backoff.v5@v5.0.3.zip\' has sha256 checksum \'a9d1a38e5cbf725ccc503febff019fda32deaded92a514a4b613e106ba515a42\' when \'58e4d901
00:52:02.2198  c2e2685426 ip-10-185-118-182   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Failed
00:52:02.4243  e032732d06 ip-10-185-125-161   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Failed
```

## A10. 2026-09-24T00:52:46Z — robotics-sdk — gomod://github.com/cloudflare/circl

- recipe/task: `nerdctl-v2.3.1-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-03e3de1e4d66eff15` host `ip-10-185-119-122` job 107441032512 (build-pr / iq-8275-evk/debug_full_linux-qcom-next, cancelled): first checksum warning at +0 ms
- runner `i-0c8c39b82a3ef4f94` host `ip-10-185-122-56` job 107441032499 (build-pr / iq-9075-evk/qcom-robotics-distro_full_linux-qcom-, cancelled): first checksum warning at +790 ms

```
00:51:06.8912  e4d66eff15 ip-10-185-119-122   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:52:18.6261  82a3ef4f94 ip-10-185-122-56    NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:52:46.5510  e4d66eff15 ip-10-185-119-122   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/cloudflare/circl;version=v1.6.3;sha256sum=9aed6385d52ccd66e0a3b8cc093b5f0e7744640485405dd08c8ef89ef6bbeb06 - will attempt other sources if available
00:52:47.3423  82a3ef4f94 ip-10-185-122-56    WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/cloudflare/circl;version=v1.6.3;sha256sum=9aed6385d52ccd66e0a3b8cc093b5f0e7744640485405dd08c8ef89ef6bbeb06 - will attempt other sources if available
00:52:48.1039  e4d66eff15 ip-10-185-119-122   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum mismatch for local file /downloads/github.com.cloudflare.circl@v1.6.3.zip
00:52:48.1040  e4d66eff15 ip-10-185-119-122   WARNING: nerdctl-v2.3.1-r0 do_fetch: Renaming /downloads/github.com.cloudflare.circl@v1.6.3.zip to /downloads/github.com.cloudflare.circl@v1.6.3.zip_bad-checksum_f478a04528e7c2a8b782d9ed531d9c3e74d461be366e8a0c96e0967f14fc48d5
00:52:48.1146  e4d66eff15 ip-10-185-119-122   ERROR: nerdctl-v2.3.1-r0 do_fetch: Checksum failure fetching gomod://github.com/cloudflare/circl;version=v1.6.3;sha256sum=9aed6385d52ccd66e0a3b8cc093b5f0e7744640485405dd08c8ef89ef6bbeb06
00:52:48.1166  e4d66eff15 ip-10-185-119-122   ERROR: nerdctl-v2.3.1-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/github.com.cloudflare.circl@v1.6.3.zip\' has sha256 checksum \'f478a04528e7c2a8b782d9ed531d9c3e74d461be366e8a0c96e0967f14fc48d5\' when \'9aed6385d52
00:52:48.1177  e4d66eff15 ip-10-185-119-122   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Failed
00:52:48.2653  82a3ef4f94 ip-10-185-122-56    NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Failed
```

## A11. 2026-09-24T00:54:53Z — robotics-sdk — gomod://github.com/google/gofuzz

- recipe/task: `nerdctl-v2.3.1-r0`, storage `/efsx`, run 35938315722 attempt 1
- runner `i-04ce780dae001b5fc` host `ip-10-185-116-32` job 107441032610 (build-pr / iq-9075-evk/debug_full_linux-qcom-next, cancelled): first checksum warning at +0 ms
- runner `i-0144f0c56e23fbe52` host `ip-10-185-122-230` job 107441032541 (build-pr / iq-8275-evk/qcom-robotics-distro-catchall_base_li, cancelled): first checksum warning at +52 ms

```
00:51:08.7914  dae001b5fc ip-10-185-116-32    NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:51:10.9350  56e23fbe52 ip-10-185-122-230   NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Started
00:54:53.2808  dae001b5fc ip-10-185-116-32    WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/google/gofuzz;version=v1.2.0;sha256sum=5948f40af1923d8f98dc1d4191311030e40e0057fb255df19ebc0360f2faac16 - will attempt other sources if available
00:54:53.3329  56e23fbe52 ip-10-185-122-230   WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum failure encountered with download of gomod://github.com/google/gofuzz;version=v1.2.0;sha256sum=5948f40af1923d8f98dc1d4191311030e40e0057fb255df19ebc0360f2faac16 - will attempt other sources if available
00:54:54.1799  dae001b5fc ip-10-185-116-32    WARNING: nerdctl-v2.3.1-r0 do_fetch: Checksum mismatch for local file /downloads/github.com.google.gofuzz@v1.2.0.zip
00:54:54.1802  dae001b5fc ip-10-185-116-32    WARNING: nerdctl-v2.3.1-r0 do_fetch: Renaming /downloads/github.com.google.gofuzz@v1.2.0.zip to /downloads/github.com.google.gofuzz@v1.2.0.zip_bad-checksum_393ce54ea04178301d10bb7995b333dcffb11c7a5f55dc717e96d962ef041fc0
00:54:54.1925  dae001b5fc ip-10-185-116-32    ERROR: nerdctl-v2.3.1-r0 do_fetch: Checksum failure fetching gomod://github.com/google/gofuzz;version=v1.2.0;sha256sum=5948f40af1923d8f98dc1d4191311030e40e0057fb255df19ebc0360f2faac16
00:54:54.1956  dae001b5fc ip-10-185-116-32    ERROR: nerdctl-v2.3.1-r0 do_fetch: Bitbake Fetcher Error: ChecksumError('Checksum mismatch!\nFile: \'/downloads/github.com.google.gofuzz@v1.2.0.zip\' has sha256 checksum \'393ce54ea04178301d10bb7995b333dcffb11c7a5f55dc717e96d962ef041fc0\' when \'5948f40af1923d
00:54:54.1969  dae001b5fc ip-10-185-116-32    NOTE: recipe nerdctl-v2.3.1-r0: task do_fetch: Failed
```

## A12. 2026-09-22T04:03:38Z — meta-qcom — gomod://golang.org/x/sys

- recipe/task: `docker-compose-5.5.1-r0`, storage `/efsx`, run 35684511207 attempt 1
- runner `i-02775c88d85855e5a` host `ip-10-185-126-108` job 106608533731 (build-pr / compile_warm_up (rb3gen2-core-kit, qcom-distro, :, failure): first checksum warning at +0 ms
- runner `i-0e6ac4ded352150e1` host `ip-10-185-124-239` job 106608533600 (build-pr / compile_warm_up (glymur-crd, qcom-distro, :ci/qco, cancelled): first checksum warning at +124 ms
- runner `i-0e77085b4c12eb4a0` host `ip-10-185-123-84` job 106608533614 (build-pr / compile_warm_up (qcom-armv8a, qcom-distro, :ci/qc, cancelled): first checksum warning at +3072 ms

```
04:01:58.7736  ed352150e1 ip-10-185-124-239   2026-09-22 04:01:58 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
04:02:02.1806  b4c12eb4a0 ip-10-185-123-84    2026-09-22 04:02:02 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
04:02:05.1171  8d85855e5a ip-10-185-126-108   2026-09-22 04:02:05 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
04:03:38.3263  8d85855e5a ip-10-185-126-108   2026-09-22 04:03:38 - INFO     - WARNING: docker-compose-5.5.1-r0 do_fetch: Checksum failure encountered with download of gomod://golang.org/x/sys;version=v0.48.0;sha256sum=3a47e06431ba1e24d5b2aca3a7ce31fd13faff34df3e5d8e63f105ff9d0c1786 - will attempt other s
04:03:38.4503  ed352150e1 ip-10-185-124-239   2026-09-22 04:03:38 - INFO     - WARNING: docker-compose-5.5.1-r0 do_fetch: Checksum failure encountered with download of gomod://golang.org/x/sys;version=v0.48.0;sha256sum=3a47e06431ba1e24d5b2aca3a7ce31fd13faff34df3e5d8e63f105ff9d0c1786 - will attempt other s
04:03:41.0877  ed352150e1 ip-10-185-124-239   2026-09-22 04:03:41 - ERROR    - ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
04:03:41.0980  ed352150e1 ip-10-185-124-239   2026-09-22 04:03:41 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
04:03:41.1754  8d85855e5a ip-10-185-126-108   2026-09-22 04:03:41 - ERROR    - ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
04:03:41.1964  8d85855e5a ip-10-185-126-108   2026-09-22 04:03:41 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
04:03:41.3997  b4c12eb4a0 ip-10-185-123-84    2026-09-22 04:03:41 - INFO     - WARNING: docker-compose-5.5.1-r0 do_fetch: Checksum failure encountered with download of gomod://golang.org/x/sys;version=v0.48.0;sha256sum=3a47e06431ba1e24d5b2aca3a7ce31fd13faff34df3e5d8e63f105ff9d0c1786 - will attempt other s
04:03:43.1928  b4c12eb4a0 ip-10-185-123-84    2026-09-22 04:03:43 - ERROR    - ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
04:03:43.2064  b4c12eb4a0 ip-10-185-123-84    2026-09-22 04:03:43 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
```

# B. Re-failures on an already corrupt `.tmp` (sequential, not simultaneous)

## B1. 2026-09-24T16:05:33Z — robotics-sdk — 

- recipe/task: ``, storage `/efsx`, run 35938315722 attempt 4
- runner `i-06bca5db4cabf49ab` host `ip-10-185-116-229` job 107711490178 (build-pr / iq-8275-evk/performance_full_linux-qcom-next, failure): first checksum warning at +0 ms
- runner `i-02ef9e4c9c898caa1` host `ip-10-185-115-27` job 107711490210 (build-pr / iq-9075-evk/performance_base_linux-qcom-next, cancelled): first checksum warning at +2927 ms

```
16:05:33.4470  b4cabf49ab ip-10-185-116-229        1933:                        # early checksum verify, so that if checksum mismatched,
16:05:33.4487  b4cabf49ab ip-10-185-116-229        0721:        except zipfile.BadZipFile:
16:05:33.4501  b4cabf49ab ip-10-185-116-229   Exception: zlib.error: Error -3 while decompressing data: invalid stored block lengths
16:05:36.3747  c9c898caa1 ip-10-185-115-27         1933:                        # early checksum verify, so that if checksum mismatched,
16:05:36.3762  c9c898caa1 ip-10-185-115-27         0721:        except zipfile.BadZipFile:
16:05:36.3784  c9c898caa1 ip-10-185-115-27    Exception: zlib.error: Error -3 while decompressing data: invalid stored block lengths
```

## B2. 2026-09-24T16:06:53Z — robotics-sdk — 

- recipe/task: ``, storage `/efsx`, run 35938315722 attempt 4
- runner `i-00397304abce07766` host `ip-10-185-112-248` job 107711490264 (build-pr / iq-9075-evk/qcom-robotics-distro-catchall_full_li, cancelled): first checksum warning at +0 ms
- runner `i-05850c4bbf23ead12` host `ip-10-185-124-122` job 107711490298 (build-pr / iq-9075-evk/performance_full_linux-qcom-next, cancelled): first checksum warning at +4516 ms

```
16:06:53.8850  4abce07766 ip-10-185-112-248        1933:                        # early checksum verify, so that if checksum mismatched,
16:06:53.8866  4abce07766 ip-10-185-112-248        0721:        except zipfile.BadZipFile:
16:06:53.8878  4abce07766 ip-10-185-112-248   Exception: zlib.error: Error -3 while decompressing data: invalid stored block lengths
16:06:58.4011  bbf23ead12 ip-10-185-124-122        1933:                        # early checksum verify, so that if checksum mismatched,
16:06:58.4028  bbf23ead12 ip-10-185-124-122        0721:        except zipfile.BadZipFile:
16:06:58.4054  bbf23ead12 ip-10-185-124-122   Exception: zlib.error: Error -3 while decompressing data: invalid stored block lengths
```

## B3. 2026-09-22T04:04:37Z — meta-qcom — docker-compose-5.5.1-r0

- recipe/task: `docker-compose-5.5.1-r0`, storage `/efsx`, run 35684511207 attempt 1
- runner `i-0e6ac4ded352150e1` host `ip-10-185-124-239` job 106608533600 (build-pr / compile_warm_up (glymur-crd, qcom-distro, :ci/qco, cancelled): first checksum warning at +0 ms
- runner `i-02775c88d85855e5a` host `ip-10-185-126-108` job 106608533731 (build-pr / compile_warm_up (rb3gen2-core-kit, qcom-distro, :, failure): first checksum warning at +11480 ms

```
04:01:58.7736  ed352150e1 ip-10-185-124-239   2026-09-22 04:01:58 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
04:02:05.1171  8d85855e5a ip-10-185-126-108   2026-09-22 04:02:05 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
04:03:41.0980  ed352150e1 ip-10-185-124-239   2026-09-22 04:03:41 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
04:03:41.1964  8d85855e5a ip-10-185-126-108   2026-09-22 04:03:41 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
04:04:37.3555  ed352150e1 ip-10-185-124-239   ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
04:04:48.8365  8d85855e5a ip-10-185-126-108   ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
```

## B4. 2026-09-27T18:35:20Z — meta-qcom — gomod://golang.org/x/sys

- recipe/task: `docker-compose-5.5.1-r0`, storage `/efsx`, run 36340100617 attempt 1
- runner `i-0854d15b61965a371` host `ip-10-185-118-156` job 108678513943 (build-pr / compile_warm_up (qcom-armv8a, qcom-distro, :ci/qc, cancelled): first checksum warning at +0 ms
- runner `i-0838bf436f1da12a2` host `ip-10-185-125-130` job 108678514009 (build-pr / compile_warm_up (rb3gen2-core-kit, qcom-distro, :, failure): first checksum warning at +22021 ms

```
18:35:03.6153  b61965a371 ip-10-185-118-156   2026-09-27 18:35:03 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
18:35:20.6164  b61965a371 ip-10-185-118-156   2026-09-27 18:35:20 - INFO     - WARNING: docker-compose-5.5.1-r0 do_fetch: Checksum failure encountered with download of gomod://golang.org/x/sys;version=v0.48.0;sha256sum=3a47e06431ba1e24d5b2aca3a7ce31fd13faff34df3e5d8e63f105ff9d0c1786 - will attempt other s
18:35:23.5373  b61965a371 ip-10-185-118-156   2026-09-27 18:35:23 - ERROR    - ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
18:35:23.5698  b61965a371 ip-10-185-118-156   2026-09-27 18:35:23 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
18:35:24.4105  36f1da12a2 ip-10-185-125-130   2026-09-27 18:35:24 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Started
18:35:42.6371  36f1da12a2 ip-10-185-125-130   2026-09-27 18:35:42 - INFO     - WARNING: docker-compose-5.5.1-r0 do_fetch: Checksum failure encountered with download of gomod://golang.org/x/sys;version=v0.48.0;sha256sum=3a47e06431ba1e24d5b2aca3a7ce31fd13faff34df3e5d8e63f105ff9d0c1786 - will attempt other s
18:35:44.7268  36f1da12a2 ip-10-185-125-130   2026-09-27 18:35:44 - ERROR    - ERROR: docker-compose-5.5.1-r0 do_fetch: Fetcher failure for URL: 'https://proxy.golang.org/golang.org/x/sys/%40v/v0.48.0.zip'. Checksum mismatch!
18:35:44.7715  36f1da12a2 ip-10-185-125-130   2026-09-27 18:35:44 - INFO     - NOTE: recipe docker-compose-5.5.1-r0: task do_fetch: Failed
```

