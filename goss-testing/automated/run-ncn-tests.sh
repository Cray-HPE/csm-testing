function run_ncn_tests {
  export NODE=$1
  port=$2
  endpoint=$3

  echo
  echo Running tests against node $'\e[1;33m'$NODE$'\e[0m'
  url=http://$NODE.hmn:$port/$endpoint

  echo Server URL: $url
  results=`curl -s {$url}`

  if [[ $? == 0 ]]; then
    if ! `echo $results | jq -e > /dev/null 2>&1`; then
      echo $'\e[1;31m'ERROR: Output not valid JSON$'\e[0m'
      return 1
    else
      echo $results | jq -c '.results | sort_by(.result) | .[]' | while read -r test; do
        result=$(echo $test | jq -r '.result')

        if [ -z $result ]; then
          continue
        elif [ $result == 0 ]; then
          result=PASS
          echo $'\e[1;32m'
        else
          result=FAIL
          echo $'\e[1;31m'
        fi

        title=$(echo $test | jq -r '.title')
        description=$(echo $test | jq -r '.meta.desc')
        severity=$(echo $test | jq -r '.meta.sev')
        summary=$(echo $test | jq -r '."summary-line"')
        time=$(echo $test | jq -r '.duration')
        time=$(echo "scale=8; $time/1000000000" | bc | awk '{printf "%.8f\n", $0}')

        echo "Result: $result"
        echo "Test Name: $title"
        echo "Description: $description"
        echo "Severity: $severity"
        echo "Test Summary: $summary"
        echo "Execution Time: $time seconds"
        echo "Node: $NODE"
      done
    fi

    echo $'\e[0m'

    total=$(echo $results | jq -r '.summary."test-count"')
    failed=$(echo $results | jq -r '.summary."failed-count"')
    time=$(echo $results | jq -r '.summary."total-duration"')
    time=$(echo "scale=4; $time/1000000000" | bc | awk '{printf "%.4f\n", $0}')

    echo "Total Tests: $total, Total Passed: $((total-failed)), Total Failed: $failed, Total Execution Time: $time seconds"
  else
    echo $'\e[1;31m'ERROR: Server endpoint could not be reached$'\e[0m'
  fi
  return 0
}