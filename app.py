"""Development entry point. Feature modules live in stride/."""
import os
from stride import create_app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=os.environ.get('FLASK_DEBUG') == '1')
