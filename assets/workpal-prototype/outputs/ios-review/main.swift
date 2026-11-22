import UIKit
import WebKit
class ReviewController:UIViewController {
  override func viewDidLoad(){super.viewDidLoad();let web=WKWebView(frame:view.bounds);web.autoresizingMask=[.flexibleWidth,.flexibleHeight];view.addSubview(web);let url=Bundle.main.url(forResource:"Workpal",withExtension:"html")!;web.loadFileURL(url,allowingReadAccessTo:url.deletingLastPathComponent())}
}
class AppDelegate:UIResponder,UIApplicationDelegate {
 var window:UIWindow?
 func application(_ application:UIApplication,didFinishLaunchingWithOptions options:[UIApplication.LaunchOptionsKey:Any]?)->Bool{window=UIWindow(frame:UIScreen.main.bounds);window?.rootViewController=ReviewController();window?.makeKeyAndVisible();return true}
}
UIApplicationMain(CommandLine.argc,CommandLine.unsafeArgv,nil,NSStringFromClass(AppDelegate.self))
