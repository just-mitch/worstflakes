import requests
from bs4 import BeautifulSoup


def main():
    # use requests to go get "http://ci.aztec-labs.com/?filter=^next&filter_prop=name&fail_list=failed_tests_next"
    response = requests.get(
        "http://ci.aztec-labs.com/?filter=^next&filter_prop=name&fail_list=failed_tests_next"
    )

    # extract the body of the response
    body = response.text
    # parse the body as html
    soup = BeautifulSoup(body, "html.parser")
    # treat the body as a list of lines
    lines = body.split("\n")
    # find the lines that end in (target: next)
    for line in lines:
        if line.endswith("(target: next)"):
            print(line)


if __name__ == "__main__":
    main()
