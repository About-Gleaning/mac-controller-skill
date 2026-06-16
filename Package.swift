// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "MacControllerSkill",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "reminders-cli", targets: ["RemindersCLI"]),
    ],
    targets: [
        .target(name: "RemindersCore"),
        .executableTarget(
            name: "RemindersCLI",
            dependencies: ["RemindersCore"]
        ),
        .testTarget(
            name: "RemindersCoreTests",
            dependencies: ["RemindersCore"]
        ),
    ]
)
