"""
Static File Server - Serves HTML, CSS, and JavaScript files
Handles serving frontend assets from the same directory
"""

import os
import unittest
from sanic import Sanic
from sanic.response import file, text
from sanic.exceptions import NotFound


def setup_static_routes(app: Sanic):
    """Setup routes for serving static files"""

    # All static files are now in src/ directory
    # Get the absolute directory where this script is located (src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    @app.route("/")
    @app.route("/index.html", name="index_html")
    async def index(_request):
        """Serve the high-performance HTML page"""
        try:
            return await file(os.path.join(script_dir, "index.html"), mime_type="text/html")
        except FileNotFoundError as exc:
            raise NotFound("index.html not found") from exc
    
    # Legacy route for old version (if needed for debugging)
    @app.route("/v1", name="index_v1")
    @app.route("/old.html", name="index_old")
    async def index_old(_request):
        """Serve the old HTML page (legacy)"""
        try:
            return await file(os.path.join(script_dir, "index.html"), mime_type="text/html")
        except FileNotFoundError as exc:
            raise NotFound("index.html not found") from exc

    @app.route("/styles.css")
    async def styles(_request):
        """Serve CSS file"""
        try:
            return await file(os.path.join(script_dir, "styles.css"), mime_type="text/css")
        except FileNotFoundError:
            return text("/* CSS file not found */", content_type="text/css", status=404)

    @app.route("/app.js")
    async def app_js(_request):
        """Serve main JavaScript file"""
        try:
            app_js_path = os.path.join(script_dir, "app.js")
            return await file(app_js_path, mime_type="application/javascript")
        except FileNotFoundError:
            return text("// app.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/polling.js")
    async def polling_js(_request):
        """Serve polling JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "polling.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// polling.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/ui.js")
    async def ui_js(_request):
        """Serve UI JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "ui.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// ui.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/init.js")
    async def init_js(_request):
        """Serve initialization JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "init.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// init.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/utils.js")
    async def utils_js(_request):
        """Serve utility JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "utils.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// utils.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/search.js")
    async def search_js(_request):
        """Serve search JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "search.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// search.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/websocket.js")
    async def websocket_js(_request):
        """Serve websocket JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "websocket.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// websocket.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/components.js")
    async def components_js(_request):
        """Serve components JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "components.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// components.js file not found",
                       content_type="application/javascript", status=404)

    # High-performance architecture files
    @app.route("/state-manager.js", name="state_manager_js")
    async def state_manager_js(_request):
        """Serve state manager JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "state-manager.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// state-manager.js file not found",
                       content_type="application/javascript", status=404)
    
    @app.route("/virtual-list.js", name="virtual_list_js")
    async def virtual_list_js(_request):
        """Serve virtual list JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "virtual-list.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// virtual-list.js file not found",
                       content_type="application/javascript", status=404)
    
    @app.route("/data-processor.worker.js", name="data_processor_worker_js")
    async def data_processor_worker_js(_request):
        """Serve data processor web worker file"""
        try:
            return await file(os.path.join(script_dir, "data-processor.worker.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// data-processor.worker.js file not found",
                       content_type="application/javascript", status=404)
    
    @app.route("/constants.js", name="constants_js")
    async def constants_js(_request):
        """Serve constants JavaScript file"""
        try:
            return await file(os.path.join(script_dir, "constants.js"),
                             mime_type="application/javascript")
        except FileNotFoundError:
            return text("// constants.js file not found",
                       content_type="application/javascript", status=404)

    @app.route("/favicon.ico")
    async def favicon(_request):
        """Serve favicon or return 404"""
        try:
            # Favicon should be in parent directory (root)
            root_dir = os.path.dirname(script_dir)
            return await file(os.path.join(root_dir, "favicon.ico"),
                             mime_type="image/x-icon")
        except FileNotFoundError as exc:
            raise NotFound("Favicon not available") from exc


class TestStaticFiles(unittest.TestCase):
    """Test cases for static file handling"""

    def test_setup_static_routes_function_exists(self):
        """Test that setup_static_routes function is callable"""
        self.assertTrue(callable(setup_static_routes))

    def test_setup_static_routes_requires_app(self):
        """Test that setup_static_routes requires a Sanic app"""
        app = Sanic("test")
        # Should not raise any exceptions
        setup_static_routes(app)

        # Check that routes were added
        route_names = [route.name for route in app.router.routes_all.values()]
        expected_routes = ['index', 'styles', 'app_js', 'polling_js', 'ui_js', 'init_js',
                          'utils_js', 'search_js', 'websocket_js', 'components_js', 'favicon']

        for expected_route in expected_routes:
            # Check if any route contains the expected name
            self.assertTrue(
                any(expected_route in route_name for route_name in route_names),
                f"Route containing '{expected_route}' not found in {route_names}"
            )

    def test_script_directory_resolution(self):
        """Test that script directory can be resolved"""
        script_dir = os.path.dirname(__file__)
        self.assertTrue(os.path.isdir(script_dir))
        self.assertTrue(os.path.isabs(script_dir) or script_dir == "")
