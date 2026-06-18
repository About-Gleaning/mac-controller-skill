// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "MacControllerSkill",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "calendar-cli", targets: ["CalendarCLI"]),
        .executable(name: "notifications-cli", targets: ["NotificationsCLI"]),
        .executable(name: "reminders-cli", targets: ["RemindersCLI"]),
    ],
    targets: [
        .target(name: "CalendarCore"),
        .executableTarget(
            name: "CalendarCLI",
            dependencies: ["CalendarCore"],
            exclude: ["Info.plist"],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Sources/CalendarCLI/Info.plist",
                ])
            ]
        ),
        .target(name: "NotificationCore"),
        .executableTarget(
            name: "NotificationsCLI",
            dependencies: ["NotificationCore"],
            exclude: ["Info.plist"],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Sources/NotificationsCLI/Info.plist",
                ])
            ]
        ),
        .target(name: "RemindersCore"),
        .executableTarget(
            name: "RemindersCLI",
            dependencies: ["RemindersCore"]
        ),
        .testTarget(
            name: "CalendarCoreTests",
            dependencies: ["CalendarCore"]
        ),
        .testTarget(
            name: "NotificationCoreTests",
            dependencies: ["NotificationCore"]
        ),
        .testTarget(
            name: "RemindersCoreTests",
            dependencies: ["RemindersCore"]
        ),
    ]
)
