# Third-Party Notices

The original skill, wrapper, scanner implementation, installer, tests and documentation in this repository use the MIT license in LICENSE.

The installer downloads the database-query CLI from https://github.com/huohuoer/wechat-cli at commit `a3789232d4f79bf0b30634d9dadbce71e4acd601` under Apache License 2.0. The source archive includes its upstream LICENSE and is installed separately; it is not redistributed in this repository. The archive's SHA256 is `3f3e858d957669528b3f4769296847853d3945ac2ab90a92f2ad6064d0faf4cb`.

Installed dependencies: Click (BSD-3-Clause), PyCryptodome (BSD/Public Domain components; see its distribution), and Zstandard Python bindings (BSD-3-Clause; bundled Zstandard has its own license). Their packages retain their respective notices. These packages are not bundled in the release archive.

The Windows Config.Cipher workflow was informed by the WorkBuddy skill description supplied by the user and publicly documented SQLCipher page authentication behavior. The user-supplied scripts contain machine-specific paths and have no verified redistribution license in their local metadata. They are not copied or distributed. The bounded scanner and profile helpers here are newly implemented; no claim of universal WeChat compatibility is made.

WeChat and WorkBuddy belong to their respective owners. No WeChat installer, proprietary client code, account identifiers, keys or chat records are included.
