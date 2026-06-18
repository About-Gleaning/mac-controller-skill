import XCTest
@testable import NotificationCore

final class NotificationCoreTests: XCTestCase {
    func testParseAuthStatus() throws {
        let command = try CommandParser(arguments: ["auth-status"]).parse()
        XCTAssertEqual(command, .authStatus)
    }

    func testParseRequestAccess() throws {
        let command = try CommandParser(arguments: ["request-access"]).parse()
        XCTAssertEqual(command, .requestAccess)
    }

    func testParseSendWithTitleOnly() throws {
        let command = try CommandParser(arguments: ["send", "--title", "测试通知"]).parse()
        XCTAssertEqual(command, .send(SendOptions(title: "测试通知", subtitle: nil, body: nil)))
    }

    func testParseSendWithOptionalContent() throws {
        let command = try CommandParser(arguments: ["send", "--title", "构建完成", "--subtitle", "mac-controller-skill", "--body", "可以查看结果"]).parse()
        XCTAssertEqual(command, .send(SendOptions(title: "构建完成", subtitle: "mac-controller-skill", body: "可以查看结果")))
    }

    func testRejectsSendWithoutTitle() {
        XCTAssertThrowsError(try CommandParser(arguments: ["send", "--body", "缺少标题"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "缺少必填参数 --title。")
        }
    }

    func testRejectsUnusedArgument() {
        XCTAssertThrowsError(try CommandParser(arguments: ["send", "--title", "测试通知", "--extra", "x"]).parse()) { error in
            XCTAssertEqual((error as? CLIError)?.message, "无法识别参数：--extra x。")
        }
    }

    func testSuccessJsonUsesExpectedKeys() {
        let json = encodeSuccess(SendData(notificationID: "id-1", delivered: true))
        XCTAssertTrue(json.contains("\"notification_id\":\"id-1\""))
        XCTAssertTrue(json.contains("\"delivered\":true"))
    }

    func testAuthStatusJsonUsesSnakeCaseKeys() {
        let data = notificationAuthData(status: .notDetermined)
        let json = encodeSuccess(data)
        XCTAssertTrue(json.contains("\"service\":\"notifications\""))
        XCTAssertTrue(json.contains("\"status\":\"not_determined\""))
        XCTAssertTrue(json.contains("\"authorized\":false"))
        XCTAssertTrue(json.contains("\"next_steps\""))
    }
}
