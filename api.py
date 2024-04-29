import logging
from flask import Flask, request
from utils import success_json_response, return_error, return_specific_error
from vision import get_gate_status

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)-10s) %(message)s')
logger = logging.getLogger(__name__)

@app.route("/gate/status", methods=["GET"])
def gate_status():
  debug = request.args.get("debug")
  status = {}
  if debug:
    status = get_gate_status(debug=True)
  else:
    status = get_gate_status(debug=False)
  return success_json_response(status)

if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=5001, threaded=True)