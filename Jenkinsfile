@Library('dst-shared') _

def skipSuccess = false

pipeline {
    agent { label "dstbuild" }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }

    stages {

		stage('PREP: Environment') {
		    steps {
		        script {
		            // Define these vars here so they're mutable (vs. global).
                    //env.VERSION = sh(returnStdout: true, script: "cat .version").trim()
                    env.BUILD_DATE = sh(returnStdout: true, script: "date -u '+%Y%m%d%H%M%S'").trim()
                    env.GIT_TAG = sh(returnStdout: true, script: "git rev-parse --short HEAD").trim()
                    env.GIT_REPO_NAME = sh(returnStdout: true, script: "basename -s .git ${GIT_URL}").trim()
                    slackNotify(channel: "metal-ci-alerts", credential: "", color: "#cccccc", message: "Repo: *${env.GIT_REPO_NAME}*\nBranch: *${env.GIT_BRANCH}*\nBuild: ${env.BUILD_URL}\nStatus: `STARTING`")
                }
            }
        }
        stage('Validate'){
            steps {
                echo "Running no-op for PR requests build condition."
                sh "echo 'no-op'"
            }
        }
    }
	post('Post Run Conditions') {
        always {
            script {
                currentBuild.result = currentBuild.result == null ? "SUCCESS" : currentBuild.result
            }
        }

		fixed {
            notifyBuildResult(headline: "FIXED")
			script {
				slackNotify(channel: "metal-ci-alerts", credential: "", color: "#1d9bd1", message: "Repo: *${env.GIT_REPO_NAME}*\nBranch: *${env.GIT_BRANCH}*\nBuild: ${env.BUILD_URL}\nStatus: `FIXED`")
                // Set to true so the 'success' post section is skipped when the build result is 'fixed'
                // Otherwise both 'fixed' and 'success' sections will execute due to Jenkins behavior
                skipSuccess = true
			}

			// Delete the 'build' directory
			dir('build') {
				// the 'deleteDir' command recursively deletes the
				// current directory
				deleteDir()
			}
		}

		success {
			script {
                if (skipSuccess != true) {
                    slackNotify(channel: "metal-ci-alerts", credential: "", color: "good", message: "Repo: *${env.GIT_REPO_NAME}*\nBranch: *${env.GIT_BRANCH}*\nBuild: ${env.BUILD_URL}\nStatus: `${currentBuild.result}`")
                }
			}

			// Delete the 'build' directory
			dir('build') {
				// the 'deleteDir' command recursively deletes the
				// current directory
				deleteDir()
			}
		}

		failure {
            notifyBuildResult(headline: "FAILED")
			script {
				slackNotify(channel: "metal-ci-alerts", credential: "", color: "danger", message: "Repo: *${env.GIT_REPO_NAME}*\nBranch: *${env.GIT_BRANCH}*\nBuild: ${env.BUILD_URL}\nStatus: `${currentBuild.result}`")
			}

			// Delete the 'build' directory
			dir('build') {
				// the 'deleteDir' command recursively deletes the
				// current directory
				deleteDir()
			}
		}
	}
}
