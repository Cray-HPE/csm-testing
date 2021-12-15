# Copyright 2014-2021 Hewlett Packard Enterprise Development LP
command:
  k8s_postgresql_backups_check:
    title: Kubernetes Postgresql Check that Automated Backups are Working
    meta:
      desc: If this test fails, run the script "goss-testing/scripts/postgresql_backups_check.sh -p" to see a printed description of the errors. Check that cron jobs are running and creating postgresql backups periodically with the command "kubectl get cronjob -A | grep postgresql". To see a last scheduled time, run the command "kubectl -n <namespace> get cronjob <cron_job_name> -o jsonpath='{.status}'".
      sev: 0
    exec: "{{.Env.GOSS_BASE}}/scripts/postgresql_backups_check.sh"
    exit-status: 0
    stdout:
      - PASS
    timeout: 600000
    skip: false
