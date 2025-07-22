#!/usr/bin/env python3
"""
Docker environment PDF export adapter
Process special requirements for PDF generation in Docker containers
"""

import os
import subprocess
import tempfile
from typing import Optional

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

def is_docker_environment() -> bool:
    """Check if running in Docker environment"""
    try:
        # Check /.dockerenv file
        if os.path.exists('/.dockerenv'):
            return True
        
        # Check cgroup information
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content:
                return True
    except:
        pass
    
    # Check environment variables
    return os.environ.get('DOCKER_CONTAINER', '').lower() == 'true'

def setup_xvfb_display():
    """Set up virtual display (required for Docker environment)"""
    if not is_docker_environment():
        return True

    try:
        # Check if Xvfb is already running
        try:
            result = subprocess.run(['pgrep', 'Xvfb'], capture_output=True, timeout=2)
            if result.returncode == 0:
                logger.info(f"✅ Xvfb is already running")
                os.environ['DISPLAY'] = ':99'
                return True
        except:
            pass

        # Start Xvfb virtual display (run in background)
        subprocess.Popen([
            'Xvfb', ':99', '-screen', '0', '1024x768x24', '-ac', '+extension', 'GLX'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait a bit for Xvfb to start
        import time
        time.sleep(2)

        # Set DISPLAY environment variable
        os.environ['DISPLAY'] = ':99'
        logger.info(f"✅ Docker virtual display set successfully")
        return True
    except Exception as e:
        logger.error(f"⚠️ Virtual display setup failed: {e}")
        # Even if Xvfb fails, try to continue, as wkhtmltopdf can run headless in some cases
        return False

def get_docker_wkhtmltopdf_args():
    """Get special parameters for wkhtmltopdf in Docker environment"""
    if not is_docker_environment():
        return []

    # These are wkhtmltopdf parameters, not pandoc parameters
    return [
        '--disable-smart-shrinking',
        '--print-media-type',
        '--no-background',
        '--disable-javascript',
        '--quiet'
    ]

def test_docker_pdf_generation() -> bool:
    """Test PDF generation in Docker environment"""
    if not is_docker_environment():
        return True
    
    try:
        import pypandoc

        
        # Set up virtual display
        setup_xvfb_display()
        
        # Test content
        test_html = """
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Docker PDF Test</title>
        </head>
        <body>
            <h1>Docker PDF Test</h1>
            <p>This is a PDF test document generated in a Docker environment.</p>
            <p>Chinese character test: Hello World!</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            output_file = tmp.name
        
        # Use simplified parameters for Docker environment
        extra_args = [
            '--pdf-engine=wkhtmltopdf',
            '--pdf-engine-opt=--disable-smart-shrinking',
            '--pdf-engine-opt=--quiet'
        ]

        pypandoc.convert_text(
            test_html,
            'pdf',
            format='html',
            outputfile=output_file,
            extra_args=extra_args
        )
        
        # Check if file was generated
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            os.unlink(output_file)  # Clean up test file
            logger.info(f"✅ Docker PDF generation test successful")
            return True
        else:
            logger.error(f"❌ Docker PDF generation test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Docker PDF test failed: {e}")
        return False

def get_docker_pdf_extra_args():
    """Get additional parameters for PDF generation in Docker environment"""
    base_args = [
        '--toc',
        '--number-sections',
        '-V', 'geometry:margin=2cm',
        '-V', 'documentclass=article'
    ]

    if is_docker_environment():
        # Special configuration for Docker environment - use correct pandoc parameters
        docker_args = []
        wkhtmltopdf_args = get_docker_wkhtmltopdf_args()

        # Pass wkhtmltopdf parameters correctly to pandoc
        for arg in wkhtmltopdf_args:
            docker_args.extend(['--pdf-engine-opt=' + arg])

        return base_args + docker_args

    return base_args

def check_docker_pdf_dependencies():
    """Check dependencies for PDF generation in Docker environment"""
    if not is_docker_environment():
        return True, "Non-Docker environment"
    
    missing_deps = []
    
    # Check wkhtmltopdf
    try:
        result = subprocess.run(['wkhtmltopdf', '--version'], 
                              capture_output=True, timeout=10)
        if result.returncode != 0:
            missing_deps.append('wkhtmltopdf')
    except:
        missing_deps.append('wkhtmltopdf')
    
    # Check Xvfb
    try:
        result = subprocess.run(['Xvfb', '-help'], 
                              capture_output=True, timeout=10)
        if result.returncode not in [0, 1]:  # Xvfb -help returns 1 is normal
            missing_deps.append('xvfb')
    except:
        missing_deps.append('xvfb')
    
    # Check fonts
    font_paths = [
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/liberation/'
    ]
    
    font_found = any(os.path.exists(path) for path in font_paths)
    if not font_found:
        missing_deps.append('chinese-fonts')
    
    if missing_deps:
        return False, f"Missing dependencies: {', '.join(missing_deps)}"
    
    return True, "All dependencies installed"

def get_docker_status_info():
    """Get Docker environment status information"""
    info = {
        'is_docker': is_docker_environment(),
        'dependencies_ok': False,
        'dependency_message': '',
        'pdf_test_ok': False
    }
    
    if info['is_docker']:
        info['dependencies_ok'], info['dependency_message'] = check_docker_pdf_dependencies()
        if info['dependencies_ok']:
            info['pdf_test_ok'] = test_docker_pdf_generation()
    else:
        info['dependencies_ok'] = True
        info['dependency_message'] = 'Non-Docker environment, using standard configuration'
        info['pdf_test_ok'] = True
    
    return info

if __name__ == "__main__":
    logger.info(f"🐳 Docker PDF adapter test")
    logger.info(f"=")
    
    status = get_docker_status_info()
    
    logger.info(f"Docker environment: {'Yes' if status['is_docker'] else 'No'}")
    logger.error(f"Dependency check: {'✅' if status['dependencies_ok'] else '❌'} {status['dependency_message']}")
    logger.error(f"PDF test: {'✅' if status['pdf_test_ok'] else '❌'}")
    
    if status['is_docker'] and status['dependencies_ok'] and status['pdf_test_ok']:
        logger.info(f"\n🎉 Docker PDF functionality fully normal!")
    elif status['is_docker'] and not status['dependencies_ok']:
        logger.warning(f"\n⚠️ Docker environment missing PDF dependencies, please rebuild image")
    elif status['is_docker'] and not status['pdf_test_ok']:
        logger.error(f"\n⚠️ Docker PDF test failed, possible configuration adjustment needed")
    else:
        logger.info(f"\n✅ Non-Docker environment, using standard PDF configuration")
