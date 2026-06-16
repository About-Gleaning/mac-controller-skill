import XCTest
@testable import CalendarCore

final class CalendarCoreTests: XCTestCase {
    func testParseAuthStatus() throws {
        let command = try CommandParser(arguments: ["auth-status"]).parse()
        XCTAssertEqual(command, .authStatus)
    }

    func testParseRequestAccess() throws {
        let command = try CommandParser(arguments: ["request-access"]).parse()
        XCTAssertEqual(command, .requestAccess)
    }

    func testParseListDefaultsToCurrentContract() throws {
        let command = try CommandParser(arguments: ["list"]).parse()
        XCTAssertEqual(command, .list(ListOptions(calendar: nil, query: nil, from: nil, to: nil, limit: 20, offset: 0)))
    }

    func testRejectsInvalidBool() {
        XCTAssertThrowsError(try CommandParser(arguments: ["create", "--title", "周会", "--start", "2026-06-18 10:00:00", "--end", "2026-06-18 11:00:00", "--all-day", "yes"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "布尔值必须是 true 或 false。")
        }
    }

    func testRejectsUnscopedLimitAboveMaximum() {
        XCTAssertThrowsError(try CommandParser(arguments: ["list", "--limit", "21"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "当前查询的 --limit 不能超过 20。请使用 --query、--calendar 或 --offset 缩小范围。")
        }
    }

    func testAllowsScopedLimitUpToFifty() throws {
        let command = try CommandParser(arguments: ["list", "--query", "周会", "--limit", "50", "--offset", "20"]).parse()
        XCTAssertEqual(command, .list(ListOptions(calendar: nil, query: "周会", from: nil, to: nil, limit: 50, offset: 20)))
    }

    func testRejectsCreateWhenEndIsNotAfterStart() {
        XCTAssertThrowsError(try CommandParser(arguments: ["create", "--title", "周会", "--start", "2026-06-18 11:00:00", "--end", "2026-06-18 10:00:00"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "--end 必须晚于 --start。")
        }
    }

    func testRejectsListWhenToIsNotAfterFrom() {
        XCTAssertThrowsError(try CommandParser(arguments: ["list", "--from", "2026-06-18 11:00:00", "--to", "2026-06-18 10:00:00"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "--end 必须晚于 --start。")
        }
    }

    func testDateRoundTrip() throws {
        let date = try XCTUnwrap(parseDate("2026-06-18 10:00:00"))
        XCTAssertEqual(formatDate(date), "2026-06-18 10:00:00")
    }

    func testSuccessJsonUsesExpectedKeys() {
        let event = EventOutput(
            id: "id-1",
            title: "团队周会",
            calendar: "工作",
            startDate: "2026-06-18 10:00:00",
            endDate: "2026-06-18 11:00:00",
            allDay: false,
            location: nil,
            notes: nil
        )
        let json = encodeSuccess(ListData(events: [event], count: 1, offset: 0, limit: 20, hasMore: false, nextOffset: nil))
        XCTAssertTrue(json.contains("\"start_date\":\"2026-06-18 10:00:00\""))
        XCTAssertTrue(json.contains("\"end_date\":\"2026-06-18 11:00:00\""))
        XCTAssertTrue(json.contains("\"all_day\":false"))
        XCTAssertTrue(json.contains("\"has_more\":false"))
    }
}
