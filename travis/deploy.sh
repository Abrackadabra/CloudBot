chmod 600 travis/yacah_deploy_key
ssh -o StrictHostKeyChecking=no -i travis/yacah_deploy_key yacahb@abra.me 'sudo restart yacah'
