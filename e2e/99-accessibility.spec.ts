import {expect,test} from '@playwright/test';
import {checkReadability,checkWorkspace} from './accessibility';

test('readable login, leave application and team inbox at five widths',async({page})=>{
  await page.goto('/');
  await expect(page.locator('input[type=password]')).toBeVisible();
  await checkReadability(page);
  await checkWorkspace(page,'employee@leaveflow.test');
  await checkWorkspace(page,'manager@leaveflow.test');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await expect(page.locator('input[type=password]')).toBeVisible();
});
