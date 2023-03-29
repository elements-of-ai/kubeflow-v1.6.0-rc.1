import { Component, OnInit, Input } from '@angular/core';
import { FormGroup, ValidatorFn, AbstractControl } from '@angular/forms';
import { Subscription } from 'rxjs';
import { GPUVendor } from 'src/app/types';
import { JWABackendService } from 'src/app/services/backend.service';

@Component({
  selector: 'app-form-gpus',
  templateUrl: './form-gpus.component.html',
  styleUrls: ['./form-gpus.component.scss'],
})
export class FormGpusComponent implements OnInit {
  @Input() parentForm: FormGroup;
  @Input() vendors: GPUVendor[] = [];

  private gpuCtrl: FormGroup;
  public installedVendors = new Set<string>();
  public vendorsNums = {};
  public vendorinfo = "";

  subscriptions = new Subscription();
  maxGPUs = 16;
  gpusCount = ['1', '2', '4', '8'];

  constructor(public backend: JWABackendService) {}

  ngOnInit() {
    this.gpuCtrl = this.parentForm.get('gpus') as FormGroup;

    // Vendor should not be empty if the user selects GPUs num
    this.parentForm
      .get('gpus')
      .get('vendor')
      .setValidators([this.vendorWithNum()]);

    // this.subscriptions.add(
    //   this.gpuCtrl.get('num').valueChanges.subscribe((n: string) => {
    //     if (n === 'none') {
    //       this.gpuCtrl.get('vendor').disable();
    //     } else {
    //       this.gpuCtrl.get('vendor').enable();
    //     }
    //   }),
    // );

    this.backend.getGPUVendors().subscribe(vendors => { 
      console.log('vendors: ', vendors)
      this.installedVendors = new Set(vendors);
      
    });

    this.backend.getGPUCount().subscribe(count => { 
      console.log('gpu count: ', count);
      this.vendorsNums = new Object(count);
      const vendorKey = Object.keys(this.vendorsNums);
      console.log('vendorKey: ', vendorKey);

      (Object.keys(this.vendorsNums)).forEach((key) => {
        console.log('$');
        console.log(key, this.vendorsNums[key]);
        this.vendorinfo += this.vendorsNums[key] + ' ' + key
      });

      console.log('this.vendorinfo: ', this.vendorinfo)
      
      // console.log('vendorKey Num: ', this.vendorsNums[vendorKey])
      // this.installedVendors = new Set(count);
      
    });
  }

  // Vendor handling
  public vendorTooltip(vendor: GPUVendor) {
    
    if (!this.installedVendors.has(vendor.limitsKey)) {
      return $localize`There are currently no ${vendor.uiName} GPUs in your cluster.`
    }
    else {
      return $localize`There are currently ${this.vendorinfo}  GPUs in your cluster.`;
    }

    // return !this.installedVendors.has(vendor.limitsKey)
    //   ? $localize`There are currently no ${vendor.uiName} GPUs in your cluster.`
    //   : $localize`There are currently ${vendor.uiName}, installedVendors: ${this.installedVendors}  GPUs in your cluster.`;
  }

  // Custom Validation
  public getVendorError() {
    const vendorCtrl = this.parentForm.get('gpus').get('vendor');

    if (vendorCtrl.hasError('vendorNullName')) {
      return $localize`You must also specify the GPU Vendor for the assigned GPUs`;
    }
  }

  private vendorWithNum(): ValidatorFn {
    // Make sure that if the user has specified a number of GPUs
    // that they also specify the GPU vendor
    return (control: AbstractControl): { [key: string]: any } => {
      const num = this.parentForm.get('gpus').get('num').value;
      const vendor = this.parentForm.get('gpus').get('vendor').value;

      if (num !== 'none' && vendor === '') {
        return { vendorNullName: true };
      } else {
        return null;
      }
    };
  }
}
