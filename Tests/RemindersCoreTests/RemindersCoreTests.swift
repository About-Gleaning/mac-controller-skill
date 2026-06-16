import XCTest
@testable import RemindersCore

final class RemindersCoreTests: XCTestCase {
    func testParseListDefaultsToCurrentContract() throws {
        let command = try CommandParser(arguments: ["list"]).parse()
        XCTAssertEqual(command, .list(ListOptions(list: nil, query: nil, completed: nil, limit: 20, offset: 0)))
    }

    func testRejectsInvalidBool() {
        XCTAssertThrowsError(try CommandParser(arguments: ["list", "--completed", "yes"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "布尔值必须是 true 或 false。")
        }
    }

    func testRejectsUnscopedLimitAboveMaximum() {
        XCTAssertThrowsError(try CommandParser(arguments: ["list", "--limit", "21"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "当前查询的 --limit 不能超过 20。请使用 --query、--list 或 --offset 缩小范围。")
        }
    }

    func testAllowsScopedLimitUpToFifty() throws {
        let command = try CommandParser(arguments: ["list", "--query", "周报", "--limit", "50", "--offset", "20"]).parse()
        XCTAssertEqual(command, .list(ListOptions(list: nil, query: "周报", completed: nil, limit: 50, offset: 20)))
    }

    func testRejectsDueAndClearDueTogether() {
        XCTAssertThrowsError(try CommandParser(arguments: ["update", "--id", "abc", "--due", "2026-06-01 09:00:00", "--clear-due"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "--clear-due 不能和 --due 同时使用。")
        }
    }

    func testDateRoundTrip() throws {
        let date = try XCTUnwrap(parseDate("2026-06-01 09:00:00"))
        XCTAssertEqual(formatDate(date), "2026-06-01 09:00:00")
    }

    func testSuccessJsonUsesExpectedKeys() {
        let reminder = ReminderOutput(
            id: "id-1",
            name: "提交周报",
            list: "提醒事项",
            body: nil,
            completed: false,
            dueDate: nil,
            priority: 0
        )
        let json = encodeSuccess(ListData(reminders: [reminder], count: 1, offset: 0, limit: 20, hasMore: false, nextOffset: nil))
        XCTAssertTrue(json.contains("\"due_date\":null"))
        XCTAssertTrue(json.contains("\"has_more\":false"))
        XCTAssertTrue(json.contains("\"next_offset\":null"))
    }
}
