// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "MacControllerSkill",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "calendar-cli", targets: ["CalendarCLI"]),
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
            name: "RemindersCoreTests",
            dependencies: ["RemindersCore"]
        ),
    ]
)
