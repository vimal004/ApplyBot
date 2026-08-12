                sock.connect(addr_info[0][4])
                return sock

            smtp_success = False
            smtp_err = None

            # Attempt 1: Explicit IPv4 on Port 587 (STARTTLS)
            try:
                sock = _create_ipv4_socket(config.email.smtp_server, config.email.smtp_port, timeout=15)
                server = smtplib.SMTP(timeout=15)
                server.sock = sock
                server.file = sock.makefile('rb')
                (code, msg_bytes) = server.getreply()
                server.starttls()
                server.login(sender_email, app_password)
                server.sendmail(sender_email, all_recipients, msg.as_string())
                server.quit()
                smtp_success = True
            except Exception as err1:
                smtp_err = err1
                print(f"[EmailSender] IPv4 SMTP 587 failed ({err1}). Retrying standard SMTP_SSL...")

            # Attempt 2: Standard SMTP_SSL on Port 465 with socket force
            if not smtp_success:
                try:
                    sock = _create_ipv4_socket("smtp.gmail.com", 465, timeout=15)
                    import ssl
                    context = ssl.create_default_context()
                    ssl_sock = context.wrap_socket(sock, server_hostname="smtp.gmail.com")
                    server = smtplib.SMTP_SSL(timeout=15)
                    server.sock = ssl_sock
                    server.file = ssl_sock.makefile('rb')
                    (code, msg_bytes) = server.getreply()
                    server.login(sender_email, app_password)
                    server.sendmail(sender_email, all_recipients, msg.as_string())
                    server.quit()
                    smtp_success = True
                except Exception as err2:
                    # Final fallback: Standard smtplib call
                    try:
                        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                            server.login(sender_email, app_password)
                            server.sendmail(sender_email, all_recipients, msg.as_string())
                            smtp_success = True
                    except Exception as err3:
                        return False, f"Failed to send email: IPv4 587 ({smtp_err}), IPv4 SSL ({err2}), Std SSL ({err3})"

            if cc_list:
                return True, f"✅ Email sent to {primary} (CC: {', '.join(cc_list)})!"
            return True, f"✅ Email sent to {primary}!"
        except Exception as e:
            return False, f"Failed to send email: {e}"
